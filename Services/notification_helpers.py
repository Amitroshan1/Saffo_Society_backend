"""Notification helpers — lookups, template render, recipients, serializers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
    ScheduledNotification,
)
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.society import Society
from Models.user import User
from Models.wing import Wing
from Utils.errors import ApiError

PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

TEMPLATE_FIELD_MAP = {
    "name": "name",
    "category": "category",
    "channel": "channel",
    "subjectTemplate": "subject_template",
    "bodyTemplate": "body_template",
    "priority": "priority",
    "isSystem": "is_system",
    "notes": "notes",
    "metadata": "metadata_json",
    "isActive": "is_active",
}


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


from Schemas.notification import render_template


async def get_template_in_society(
    db: AsyncSession, template_id: UUID, society_id: UUID
) -> NotificationTemplate:
    result = await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.society_id == society_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise ApiError(404, "Notification template not found")
    return template


async def get_template_by_code(
    db: AsyncSession, society_id: UUID, code: str
) -> NotificationTemplate | None:
    result = await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.society_id == society_id,
            NotificationTemplate.code == code,
            NotificationTemplate.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def get_notification_in_society(
    db: AsyncSession, notification_id: UUID, society_id: UUID
) -> Notification:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.society_id == society_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise ApiError(404, "Notification not found")
    return notification


async def get_delivery_in_society(
    db: AsyncSession, delivery_id: UUID, society_id: UUID
) -> NotificationDelivery:
    result = await db.execute(
        select(NotificationDelivery).where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.society_id == society_id,
        )
    )
    delivery = result.scalar_one_or_none()
    if not delivery:
        raise ApiError(404, "Notification delivery not found")
    return delivery


async def get_scheduled_in_society(
    db: AsyncSession, scheduled_id: UUID, society_id: UUID
) -> ScheduledNotification:
    result = await db.execute(
        select(ScheduledNotification).where(
            ScheduledNotification.id == scheduled_id,
            ScheduledNotification.society_id == society_id,
        )
    )
    scheduled = result.scalar_one_or_none()
    if not scheduled:
        raise ApiError(404, "Scheduled notification not found")
    return scheduled


async def get_or_create_preferences(
    db: AsyncSession,
    *,
    society_id: UUID,
    user_id: UUID,
    resident_id: UUID | None = None,
    actor_id: UUID | None = None,
) -> NotificationPreference:
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.society_id == society_id,
            NotificationPreference.user_id == user_id,
        )
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    prefs = NotificationPreference(
        society_id=society_id,
        user_id=user_id,
        resident_id=resident_id,
        email_enabled=True,
        sms_enabled=True,
        push_enabled=True,
        marketing_enabled=False,
        system_enabled=True,
        emergency_enabled=True,
        metadata_json={},
        is_active=True,
        version=1,
        created_by=actor_id or user_id,
        updated_by=actor_id or user_id,
    )
    db.add(prefs)
    await db.flush()
    return prefs


def resolve_channels_for_user(
    requested_channels: List[str],
    prefs: NotificationPreference | None,
    *,
    category: str,
    priority: str = "normal",
) -> List[str]:
    """Filter channels by user preferences. Emergency always keeps in_app."""
    channels = list(dict.fromkeys(requested_channels or ["in_app"]))
    is_emergency = category == "emergency" or priority == "critical"
    if prefs is None:
        return channels

    allowed: List[str] = []
    for channel in channels:
        if channel == "in_app":
            if is_emergency or prefs.system_enabled or category != "marketing":
                allowed.append(channel)
            continue
        if category == "marketing" and not prefs.marketing_enabled:
            continue
        if category == "emergency" and not prefs.emergency_enabled and channel != "in_app":
            # Still allow non-in_app only if emergency_enabled; in_app always below
            continue
        if channel == "email" and prefs.email_enabled:
            allowed.append(channel)
        elif channel == "sms" and prefs.sms_enabled:
            allowed.append(channel)
        elif channel == "push" and prefs.push_enabled:
            allowed.append(channel)
        elif channel == "webhook":
            allowed.append(channel)

    if is_emergency and "in_app" not in allowed:
        allowed.insert(0, "in_app")
    if not allowed and "in_app" in channels:
        allowed = ["in_app"]
    return allowed


async def resolve_recipients(
    db: AsyncSession,
    society_id: UUID,
    *,
    target_type: str,
    target_role: str | None = None,
    building_id: UUID | None = None,
    wing_id: UUID | None = None,
    flat_id: UUID | None = None,
    resident_id: UUID | None = None,
    user_id: UUID | None = None,
    resident_ids: List[UUID] | None = None,
) -> List[Dict[str, Any]]:
    """Return unique recipient dicts: user_id, resident_id, email, phone, name."""
    recipients: Dict[str, Dict[str, Any]] = {}

    def _add(
        *,
        uid: UUID | None,
        rid: UUID | None,
        email: str | None,
        phone: str | None,
        name: str | None,
    ) -> None:
        key = str(uid) if uid else f"resident:{rid}"
        if key in recipients:
            return
        recipients[key] = {
            "user_id": uid,
            "resident_id": rid,
            "email": email,
            "phone": phone,
            "name": name or "",
        }

    if target_type == "user" and user_id:
        user = (
            await db.execute(
                select(User).where(User.id == user_id, User.society_id == society_id)
            )
        ).scalar_one_or_none()
        if user:
            resident = (
                await db.execute(
                    select(Resident).where(
                        Resident.society_id == society_id, Resident.user_id == user.id
                    )
                )
            ).scalar_one_or_none()
            _add(
                uid=user.id,
                rid=resident.id if resident else None,
                email=user.email,
                phone=user.phone,
                name=user.name,
            )
        return list(recipients.values())

    if target_type == "role" and target_role:
        users = (
            await db.execute(
                select(User).where(
                    User.society_id == society_id,
                    User.role == target_role,
                    User.is_active.is_(True),
                )
            )
        ).scalars().all()
        for user in users:
            _add(
                uid=user.id,
                rid=None,
                email=user.email,
                phone=user.phone,
                name=user.name,
            )
        return list(recipients.values())

    occupancy_filter = [
        Occupancy.society_id == society_id,
        Occupancy.status == "active",
        Occupancy.is_active.is_(True),
    ]
    if target_type == "building" and building_id:
        occupancy_filter.append(Occupancy.building_id == building_id)
    elif target_type == "wing" and wing_id:
        occupancy_filter.append(Occupancy.wing_id == wing_id)
    elif target_type == "flat" and flat_id:
        occupancy_filter.append(Occupancy.flat_id == flat_id)
    elif target_type == "resident" and resident_id:
        occupancy_filter.append(Occupancy.resident_id == resident_id)
    elif target_type == "resident" and resident_ids:
        occupancy_filter.append(Occupancy.resident_id.in_(resident_ids))
    elif target_type == "society":
        pass
    elif target_type in ("building", "wing", "flat", "resident"):
        return []

    if target_type in ("society", "building", "wing", "flat", "resident"):
        if target_type == "resident" and resident_id and not resident_ids:
            resident = (
                await db.execute(
                    select(Resident).where(
                        Resident.id == resident_id,
                        Resident.society_id == society_id,
                    )
                )
            ).scalar_one_or_none()
            if resident:
                user = None
                if resident.user_id:
                    user = (
                        await db.execute(select(User).where(User.id == resident.user_id))
                    ).scalar_one_or_none()
                _add(
                    uid=resident.user_id,
                    rid=resident.id,
                    email=(user.email if user else resident.email),
                    phone=(user.phone if user else resident.phone),
                    name=resident.name,
                )
            return list(recipients.values())

        if target_type == "resident" and resident_ids:
            rows = (
                await db.execute(
                    select(Resident).where(
                        Resident.society_id == society_id,
                        Resident.id.in_(resident_ids),
                        Resident.is_active.is_(True),
                    )
                )
            ).scalars().all()
            for resident in rows:
                user = None
                if resident.user_id:
                    user = (
                        await db.execute(select(User).where(User.id == resident.user_id))
                    ).scalar_one_or_none()
                _add(
                    uid=resident.user_id,
                    rid=resident.id,
                    email=(user.email if user else resident.email),
                    phone=(user.phone if user else resident.phone),
                    name=resident.name,
                )
            return list(recipients.values())

        occ_rows = (
            await db.execute(
                select(Occupancy, Resident, User)
                .join(Resident, Resident.id == Occupancy.resident_id)
                .outerjoin(User, User.id == Resident.user_id)
                .where(*occupancy_filter)
            )
        ).all()
        for _occ, resident, user in occ_rows:
            _add(
                uid=user.id if user else resident.user_id,
                rid=resident.id,
                email=(user.email if user else resident.email),
                phone=(user.phone if user else resident.phone),
                name=resident.name,
            )

    return list(recipients.values())


async def load_society_name(db: AsyncSession, society_id: UUID) -> str:
    society = (
        await db.execute(select(Society).where(Society.id == society_id))
    ).scalar_one_or_none()
    if not society:
        return ""
    return society.display_name or society.name or ""


async def enrich_variables(
    db: AsyncSession,
    society_id: UUID,
    variables: Dict[str, Any] | None,
    *,
    resident_id: UUID | None = None,
    building_id: UUID | None = None,
    wing_id: UUID | None = None,
    flat_id: UUID | None = None,
) -> Dict[str, Any]:
    vars_out = dict(variables or {})
    if "society_name" not in vars_out:
        vars_out["society_name"] = await load_society_name(db, society_id)
    if resident_id and "resident_name" not in vars_out:
        resident = (
            await db.execute(
                select(Resident).where(
                    Resident.id == resident_id, Resident.society_id == society_id
                )
            )
        ).scalar_one_or_none()
        if resident:
            vars_out["resident_name"] = resident.name
    if building_id and "building" not in vars_out:
        building = (
            await db.execute(
                select(Building).where(
                    Building.id == building_id, Building.society_id == society_id
                )
            )
        ).scalar_one_or_none()
        if building:
            vars_out["building"] = getattr(building, "name", None) or str(building_id)
    if wing_id and "wing" not in vars_out:
        wing = (
            await db.execute(
                select(Wing).where(Wing.id == wing_id, Wing.society_id == society_id)
            )
        ).scalar_one_or_none()
        if wing:
            vars_out["wing"] = getattr(wing, "name", None) or str(wing_id)
    if flat_id and "flat" not in vars_out:
        flat = (
            await db.execute(
                select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id)
            )
        ).scalar_one_or_none()
        if flat:
            vars_out["flat"] = flat.flat_no
    return vars_out


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def template_to_dict(t: NotificationTemplate) -> Dict[str, Any]:
    return {
        "id": str(t.id),
        "societyId": str(t.society_id),
        "code": t.code,
        "name": t.name,
        "category": t.category,
        "channel": t.channel,
        "subjectTemplate": t.subject_template,
        "bodyTemplate": t.body_template,
        "priority": t.priority,
        "isSystem": t.is_system,
        "metadata": t.metadata_json or {},
        "notes": t.notes,
        "isActive": t.is_active,
        "version": t.version,
        "createdBy": str(t.created_by) if t.created_by else None,
        "updatedBy": str(t.updated_by) if t.updated_by else None,
        "lastActivityAt": _iso(t.last_activity_at),
        "createdAt": _iso(t.created_at),
        "updatedAt": _iso(t.updated_at),
    }


def notification_to_dict(n: Notification) -> Dict[str, Any]:
    return {
        "id": str(n.id),
        "societyId": str(n.society_id),
        "templateId": str(n.template_id) if n.template_id else None,
        "sourceModule": n.source_module,
        "sourceEvent": n.source_event,
        "category": n.category,
        "priority": n.priority,
        "title": n.title,
        "body": n.body,
        "payload": n.payload_json or {},
        "targetType": n.target_type,
        "targetRole": n.target_role,
        "buildingId": str(n.building_id) if n.building_id else None,
        "wingId": str(n.wing_id) if n.wing_id else None,
        "flatId": str(n.flat_id) if n.flat_id else None,
        "residentId": str(n.resident_id) if n.resident_id else None,
        "userId": str(n.user_id) if n.user_id else None,
        "status": n.status,
        "scheduledFor": _iso(n.scheduled_for),
        "sentAt": _iso(n.sent_at),
        "readAt": _iso(n.read_at),
        "archivedAt": _iso(n.archived_at),
        "metadata": n.metadata_json or {},
        "notes": n.notes,
        "isActive": n.is_active,
        "version": n.version,
        "createdBy": str(n.created_by) if n.created_by else None,
        "updatedBy": str(n.updated_by) if n.updated_by else None,
        "lastActivityAt": _iso(n.last_activity_at),
        "createdAt": _iso(n.created_at),
        "updatedAt": _iso(n.updated_at),
        "isRead": n.read_at is not None or n.status == "read",
    }


def delivery_to_dict(d: NotificationDelivery) -> Dict[str, Any]:
    return {
        "id": str(d.id),
        "societyId": str(d.society_id),
        "notificationId": str(d.notification_id),
        "channel": d.channel,
        "recipientUserId": str(d.recipient_user_id) if d.recipient_user_id else None,
        "recipientResidentId": str(d.recipient_resident_id) if d.recipient_resident_id else None,
        "recipientAddress": d.recipient_address,
        "status": d.status,
        "attemptCount": d.attempt_count,
        "maxAttempts": d.max_attempts,
        "lastAttemptAt": _iso(d.last_attempt_at),
        "deliveredAt": _iso(d.delivered_at),
        "errorMessage": d.error_message,
        "providerResponse": d.provider_response or {},
        "metadata": d.metadata_json or {},
        "createdAt": _iso(d.created_at),
        "updatedAt": _iso(d.updated_at),
    }


def preference_to_dict(p: NotificationPreference) -> Dict[str, Any]:
    return {
        "id": str(p.id),
        "societyId": str(p.society_id),
        "userId": str(p.user_id),
        "residentId": str(p.resident_id) if p.resident_id else None,
        "emailEnabled": p.email_enabled,
        "smsEnabled": p.sms_enabled,
        "pushEnabled": p.push_enabled,
        "marketingEnabled": p.marketing_enabled,
        "systemEnabled": p.system_enabled,
        "emergencyEnabled": p.emergency_enabled,
        "metadata": p.metadata_json or {},
        "isActive": p.is_active,
        "version": p.version,
        "createdAt": _iso(p.created_at),
        "updatedAt": _iso(p.updated_at),
    }


def scheduled_to_dict(s: ScheduledNotification) -> Dict[str, Any]:
    return {
        "id": str(s.id),
        "societyId": str(s.society_id),
        "templateId": str(s.template_id) if s.template_id else None,
        "title": s.title,
        "body": s.body,
        "channels": s.channels or ["in_app"],
        "targetType": s.target_type,
        "targetRole": s.target_role,
        "buildingId": str(s.building_id) if s.building_id else None,
        "wingId": str(s.wing_id) if s.wing_id else None,
        "flatId": str(s.flat_id) if s.flat_id else None,
        "residentIds": s.resident_ids or [],
        "priority": s.priority,
        "category": s.category,
        "scheduleAt": _iso(s.schedule_at),
        "recurrence": s.recurrence,
        "status": s.status,
        "lastRunAt": _iso(s.last_run_at),
        "nextRunAt": _iso(s.next_run_at),
        "createdNotificationId": (
            str(s.created_notification_id) if s.created_notification_id else None
        ),
        "metadata": s.metadata_json or {},
        "notes": s.notes,
        "isActive": s.is_active,
        "version": s.version,
        "createdBy": str(s.created_by) if s.created_by else None,
        "createdAt": _iso(s.created_at),
        "updatedAt": _iso(s.updated_at),
    }


def apply_fields(entity: Any, data: Dict[str, Any], field_map: Dict[str, str]) -> None:
    for api_key, attr in field_map.items():
        if api_key in data and data[api_key] is not None:
            setattr(entity, attr, data[api_key])
