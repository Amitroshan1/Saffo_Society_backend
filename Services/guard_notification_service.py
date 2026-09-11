"""Guard notification portal logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Schemas.notification import NotificationListQueryParams
from Services import notification_service
from Services.notification_helpers import (
    get_notification_in_society,
    notification_to_dict,
    require_society_id,
)
from Utils.audit import apply_update_audit, utcnow
from Utils.errors import ApiError


async def list_guard_notifications(
    db: AsyncSession,
    query: NotificationListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    return await notification_service.list_notifications(
        db, query, actor_society_id=society_id, user_id=actor_id
    )


async def mark_notification_read(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notification = await get_notification_in_society(db, notification_id, society_id)
    if notification.user_id and notification.user_id != actor_id:
        raise ApiError(403, "Notification does not belong to this user")
    notification.read_at = utcnow()
    notification.status = "read"
    apply_update_audit(notification, actor_id)
    await db.commit()
    publish_simple(
        "NotificationRead",
        society_id=society_id,
        entity_type="notification",
        entity_id=notification.id,
        actor_id=actor_id,
        payload={},
    )
    return {"notification": notification_to_dict(notification)}
