"""Platform announcements — fan-out via Phase 15 notification engine."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.platform import PlatformAnnouncement, PlatformAnnouncementDelivery, Tenant
from Models.user import User
from Services.platform_helpers import emit_platform_event, iso, utcnow, write_audit
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


def announcement_to_dict(a: PlatformAnnouncement) -> dict:
    return {
        "id": str(a.id),
        "title": a.title,
        "body": a.body,
        "type": a.announcement_type,
        "priority": a.priority,
        "status": a.status,
        "scheduledAt": iso(a.scheduled_at),
        "sentAt": iso(a.sent_at),
        "targetRoles": a.target_roles_json or ["admin"],
        "createdAt": iso(a.created_at),
    }


async def list_announcements(db: AsyncSession) -> List[dict]:
    rows = (
        await db.execute(
            select(PlatformAnnouncement).order_by(PlatformAnnouncement.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return [announcement_to_dict(r) for r in rows]


async def create_announcement(
    db: AsyncSession,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    row = PlatformAnnouncement(
        title=body["title"].strip(),
        body=body["body"].strip(),
        announcement_type=body.get("type") or "broadcast",
        priority=body.get("priority") or "normal",
        status="scheduled" if body.get("scheduledAt") else "draft",
        scheduled_at=body.get("scheduledAt"),
        target_roles_json=body.get("targetRoles") or ["admin"],
    )
    apply_create_audit(row, actor_id)
    db.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="announcement.create",
        resource_type="platform_announcement",
        resource_id=str(row.id),
        after=announcement_to_dict(row),
    )
    emit_platform_event(
        "PlatformAnnouncementCreated",
        entity_type="platform_announcement",
        entity_id=row.id,
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(row)
    return announcement_to_dict(row)


async def send_announcement(
    db: AsyncSession,
    announcement_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    from Schemas.notification import BroadcastRequest
    from Services import notification_service

    result = await db.execute(
        select(PlatformAnnouncement).where(PlatformAnnouncement.id == announcement_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise ApiError(404, "Announcement not found")

    tenants = (
        await db.execute(select(Tenant).where(Tenant.status == "active", Tenant.society_id.is_not(None)))
    ).scalars().all()

    deliveries = []
    for tenant in tenants:
        delivery = PlatformAnnouncementDelivery(
            announcement_id=ann.id,
            tenant_id=tenant.id,
            status="pending",
        )
        db.add(delivery)
        await db.flush()
        try:
            roles = ann.target_roles_json or ["admin"]
            # Prefer admin users via broadcast target_role
            target_role = roles[0] if roles else "admin"
            body = BroadcastRequest(
                title=ann.title,
                body=ann.body,
                targetType="role",
                targetRole=target_role,
                channels=["in_app"],
                category="system",
                priority=ann.priority if ann.priority in ("low", "normal", "high", "urgent") else "normal",
                metadata={"platformAnnouncementId": str(ann.id), "type": ann.announcement_type},
            )
            result_data = await notification_service.broadcast(
                db,
                body,
                actor_id=actor_id,
                actor_society_id=tenant.society_id,
                source_module="platform",
                source_event="PlatformAnnouncement",
            )
            delivery.status = "sent"
            delivery.recipient_count = int(result_data.get("recipientCount") or 0)
            delivery.delivered_at = utcnow()
        except Exception as exc:
            delivery.status = "failed"
            delivery.error_message = str(exc)[:2000]
        deliveries.append(
            {
                "tenantId": str(tenant.id),
                "status": delivery.status,
                "recipientCount": delivery.recipient_count,
            }
        )

    ann.status = "sent"
    ann.sent_at = utcnow()
    apply_update_audit(ann, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="announcement.send",
        resource_type="platform_announcement",
        resource_id=str(ann.id),
        after={"deliveries": len(deliveries)},
    )
    emit_platform_event(
        "PlatformAnnouncementSent",
        entity_type="platform_announcement",
        entity_id=ann.id,
        actor_id=actor_id,
        payload={"tenantCount": len(deliveries)},
    )
    await db.commit()
    data = announcement_to_dict(ann)
    data["deliveries"] = deliveries
    return data
