"""Resident notification portal — wraps shared notification service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.notification import NotificationListQueryParams, PreferenceUpdate
from Services import notification_service


async def list_resident_notifications(
    db: AsyncSession,
    query: NotificationListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await notification_service.list_resident_notifications(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def get_resident_notification(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await notification_service.get_resident_notification(
        db, notification_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def mark_notification_read(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await notification_service.mark_notification_read(
        db, notification_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def mark_all_notifications_read(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notification_service.mark_all_notifications_read(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def archive_notification(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await notification_service.archive_notification(
        db, notification_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def get_preferences(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notification_service.get_preferences(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def update_preferences(
    db: AsyncSession,
    body: PreferenceUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await notification_service.update_preferences(
        db, body, actor_id=actor_id, actor_society_id=actor_society_id
    )
