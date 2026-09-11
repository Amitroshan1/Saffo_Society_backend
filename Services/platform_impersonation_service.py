"""Audited tenant admin impersonation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import PLATFORM_ROLES
from Core.security import sign_access_token
from Models.platform import PlatformImpersonationSession
from Models.user import User
from Services.platform_helpers import emit_platform_event, iso, utcnow, write_audit
from Services.platform_settings_service import get_settings_group
from Utils.errors import ApiError


async def start_impersonation(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
    reason: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Dict[str, Any]:
    from Services.platform_tenant_service import resolve_tenant

    if actor_role not in ("super_admin", "platform_support"):
        raise ApiError(403, "Impersonation not permitted")
    if not reason or len(reason.strip()) < 5:
        raise ApiError(422, "Reason is required (min 5 characters)")

    tenant = await resolve_tenant(db, tenant_id)
    if tenant.status != "active":
        raise ApiError(422, "Can only impersonate active tenants")
    if not tenant.society_id:
        raise ApiError(422, "Tenant has no society")

    # No nested impersonation — actor must be platform user
    actor = (
        await db.execute(select(User).where(User.id == actor_id))
    ).scalar_one_or_none()
    if not actor or actor.role not in PLATFORM_ROLES:
        raise ApiError(403, "Only platform operators can impersonate")

    admin_q = await db.execute(
        select(User)
        .where(
            User.society_id == tenant.society_id,
            User.role == "admin",
            User.is_active.is_(True),
        )
        .order_by(User.created_at)
        .limit(1)
    )
    target = admin_q.scalar_one_or_none()
    if not target:
        raise ApiError(404, "No active society admin to impersonate")

    minutes = 30
    try:
        sec = await get_settings_group(db, "security")
        minutes = int((sec.get("values") or {}).get("impersonationMinutes") or 30)
    except Exception:
        pass

    now = utcnow()
    session = PlatformImpersonationSession(
        tenant_id=tenant.id,
        impersonator_id=actor_id,
        target_user_id=target.id,
        reason=reason.strip(),
        status="active",
        started_at=now,
        expires_at=now + timedelta(minutes=minutes),
        ip=ip,
        user_agent=user_agent,
    )
    db.add(session)
    await db.flush()

    token = sign_access_token(
        target.id,
        "admin",
        society_id=tenant.society_id,
        expires_minutes=minutes,
        extra={
            "impersonatorId": str(actor_id),
            "impersonationSessionId": str(session.id),
        },
    )

    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="impersonation.start",
        resource_type="tenant",
        resource_id=str(tenant.id),
        tenant_id=tenant.id,
        after={
            "sessionId": str(session.id),
            "targetUserId": str(target.id),
            "reason": reason.strip(),
        },
        ip=ip,
        user_agent=user_agent,
    )
    emit_platform_event(
        "TenantImpersonationStarted",
        tenant_id=tenant.id,
        society_id=tenant.society_id,
        entity_type="impersonation",
        entity_id=session.id,
        actor_id=actor_id,
        payload={"targetUserId": str(target.id)},
    )
    await db.commit()
    return {
        "accessToken": token,
        "expiresAt": iso(session.expires_at),
        "sessionId": str(session.id),
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "code": tenant.code,
            "societyId": str(tenant.society_id),
        },
        "targetUser": {
            "id": str(target.id),
            "name": target.name,
            "email": target.email,
            "role": "admin",
        },
        "impersonatorId": str(actor_id),
        "reason": reason.strip(),
        "banner": f"Impersonating {tenant.name} as Admin — session ends at {iso(session.expires_at)}",
    }


async def end_impersonation(
    db: AsyncSession,
    session_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
) -> Dict[str, Any]:
    result = await db.execute(
        select(PlatformImpersonationSession).where(
            PlatformImpersonationSession.id == session_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ApiError(404, "Impersonation session not found")
    if session.impersonator_id != actor_id and actor_role != "super_admin":
        raise ApiError(403, "Cannot end another operator's session")
    session.status = "ended"
    session.ended_at = utcnow()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="impersonation.end",
        resource_type="impersonation",
        resource_id=str(session.id),
        tenant_id=session.tenant_id,
    )
    emit_platform_event(
        "TenantImpersonationEnded",
        tenant_id=session.tenant_id,
        entity_type="impersonation",
        entity_id=session.id,
        actor_id=actor_id,
    )
    await db.commit()
    return {"sessionId": str(session.id), "status": "ended", "endedAt": iso(session.ended_at)}
