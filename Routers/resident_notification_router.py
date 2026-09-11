"""Resident notification portal routes — /api/v1/resident/notifications/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.notification_list_query import get_notification_list_query
from Schemas.notification import NotificationListQueryParams, PreferenceUpdate
from Services import resident_notification_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-notifications"])


@router.get("/resident/notifications")
async def resident_notifications(
    query: NotificationListQueryParams = Depends(get_notification_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.list_resident_notifications(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident notifications fetched", data)


@router.get("/resident/notifications/{notification_id}")
async def resident_get_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.get_resident_notification(
        db,
        notification_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Resident notification fetched", data)


@router.post("/resident/notifications/{notification_id}/read")
async def resident_mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.mark_notification_read(
        db,
        notification_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Notification marked as read", data)


@router.post("/resident/notifications/mark-all-read")
async def resident_mark_all_read(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.mark_all_notifications_read(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "All notifications marked as read", data)


@router.post("/resident/notifications/{notification_id}/archive")
async def resident_archive_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.archive_notification(
        db,
        notification_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Notification archived", data)


@router.get("/resident/notification-preferences")
async def resident_get_preferences(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.get_preferences(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notification preferences fetched", data)


@router.patch("/resident/notification-preferences")
async def resident_update_preferences(
    body: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notification_service.update_preferences(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notification preferences updated", data)
