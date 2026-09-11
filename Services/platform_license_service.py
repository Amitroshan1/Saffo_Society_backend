"""License engine + limit enforcement helpers."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.platform import License, Tenant
from Models.user import User
from Services.platform_helpers import (
    emit_platform_event,
    generate_license_key,
    license_to_dict,
    utcnow,
    write_audit,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


async def get_active_license(db: AsyncSession, tenant_id: UUID) -> Optional[dict]:
    result = await db.execute(
        select(License)
        .where(
            License.tenant_id == tenant_id,
            License.is_active.is_(True),
            License.status == "active",
        )
        .order_by(License.created_at.desc())
        .limit(1)
    )
    lic = result.scalar_one_or_none()
    return license_to_dict(lic) if lic else None


async def list_licenses(
    db: AsyncSession, *, tenant_id: UUID | None = None
) -> List[dict]:
    stmt = select(License).order_by(License.created_at.desc())
    if tenant_id:
        stmt = stmt.where(License.tenant_id == tenant_id)
    rows = (await db.execute(stmt.limit(200))).scalars().all()
    return [license_to_dict(r) for r in rows]


async def issue_license(
    db: AsyncSession,
    tenant_id: UUID,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    from Services.platform_tenant_service import resolve_tenant
    from Services.platform_subscription_service import get_effective_limits

    tenant = await resolve_tenant(db, tenant_id)
    # deactivate previous active
    prev = (
        await db.execute(
            select(License).where(
                License.tenant_id == tenant_id,
                License.status == "active",
            )
        )
    ).scalars().all()
    for p in prev:
        p.status = "revoked"
        p.is_active = False
        apply_update_audit(p, actor_id)

    now = utcnow()
    days = int(body.get("validDays") or 365)
    base_limits = await get_effective_limits(db, tenant)
    limits = {**base_limits, **(body.get("limits") or {})}
    features = body.get("features") or {}
    lic = License(
        tenant_id=tenant_id,
        license_key=body.get("licenseKey") or generate_license_key(),
        status="active",
        issued_at=now,
        expires_at=now + timedelta(days=days),
        limits_json=limits,
        features_json=features,
    )
    apply_create_audit(lic, actor_id)
    db.add(lic)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="license.issue",
        resource_type="license",
        resource_id=str(lic.id),
        tenant_id=tenant_id,
        after=license_to_dict(lic),
    )
    emit_platform_event(
        "LicenseIssued",
        tenant_id=tenant_id,
        entity_type="license",
        entity_id=lic.id,
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(lic)
    return license_to_dict(lic)


async def renew_license(
    db: AsyncSession, license_id: UUID, *, actor_id: UUID, actor_role: str, days: int = 365
) -> dict:
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ApiError(404, "License not found")
    base = lic.expires_at or utcnow()
    if base < utcnow():
        base = utcnow()
    lic.expires_at = base + timedelta(days=days)
    lic.status = "active"
    lic.is_active = True
    apply_update_audit(lic, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="license.renew",
        resource_type="license",
        resource_id=str(lic.id),
        tenant_id=lic.tenant_id,
        after=license_to_dict(lic),
    )
    emit_platform_event(
        "LicenseRenewed",
        tenant_id=lic.tenant_id,
        entity_type="license",
        entity_id=lic.id,
        actor_id=actor_id,
    )
    await db.commit()
    return license_to_dict(lic)


async def deactivate_license(
    db: AsyncSession, license_id: UUID, *, actor_id: UUID, actor_role: str
) -> dict:
    result = await db.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ApiError(404, "License not found")
    lic.status = "revoked"
    lic.is_active = False
    apply_update_audit(lic, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="license.deactivate",
        resource_type="license",
        resource_id=str(lic.id),
        tenant_id=lic.tenant_id,
        after=license_to_dict(lic),
    )
    emit_platform_event(
        "LicenseDeactivated",
        tenant_id=lic.tenant_id,
        entity_type="license",
        entity_id=lic.id,
        actor_id=actor_id,
    )
    await db.commit()
    return license_to_dict(lic)


async def enforce_limit(
    db: AsyncSession,
    society_id: UUID | None,
    limit_key: str,
    current_count: int | None = None,
) -> None:
    """Raise 403 if creating another entity would exceed plan/license limits."""
    if not society_id:
        return
    from Services.platform_tenant_service import resolve_tenant_by_society
    from Services.platform_subscription_service import get_effective_limits

    tenant = await resolve_tenant_by_society(db, society_id)
    if not tenant:
        return
    limits = await get_effective_limits(db, tenant)
    max_val = limits.get(limit_key)
    if max_val is None:
        return
    if current_count is None:
        if limit_key == "max_users":
            current_count = int(
                (
                    await db.execute(
                        select(func.count()).select_from(User).where(User.society_id == society_id)
                    )
                ).scalar()
                or 0
            )
        elif limit_key == "max_buildings":
            current_count = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(Building)
                        .where(Building.society_id == society_id)
                    )
                ).scalar()
                or 0
            )
        elif limit_key == "max_flats":
            current_count = int(
                (
                    await db.execute(
                        select(func.count()).select_from(Flat).where(Flat.society_id == society_id)
                    )
                ).scalar()
                or 0
            )
        else:
            return
    if current_count >= int(max_val):
        emit_platform_event(
            "LicenseLimitExceeded",
            tenant_id=tenant.id,
            society_id=society_id,
            payload={"limitKey": limit_key, "max": max_val, "current": current_count},
        )
        raise ApiError(
            403,
            f"License/plan limit reached for {limit_key} ({current_count}/{max_val})",
        )
