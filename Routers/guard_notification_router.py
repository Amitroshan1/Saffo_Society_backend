"""Guard notification portal routes — /api/v1/guard/notifications/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.notification_list_query import get_notification_list_query
from Schemas.notification import NotificationListQueryParams
from Services import guard_notification_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-notifications"])


@router.get("/guard/notifications")
async def guard_notifications(
    query: NotificationListQueryParams = Depends(get_notification_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_notification_service.list_guard_notifications(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Guard notifications fetched", data)


@router.post("/guard/notifications/mark-all-read")
async def guard_mark_all_read(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_notification_service.mark_all_notifications_read(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "All notifications marked as read", data)


@router.post("/guard/notifications/{notification_id}/read")
async def guard_mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_notification_service.mark_notification_read(
        db,
        notification_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Notification marked as read", data)
