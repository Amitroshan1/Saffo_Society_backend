"""Resident notice portal routes — /api/v1/resident/notices/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.resident_notice_list_query import get_resident_notice_list_query
from Schemas.resident_notice_schema import ResidentNoticeListQueryParams
from Services import resident_notice_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-notices"])


@router.get("/resident/notices")
async def resident_list_notices(
    query: ResidentNoticeListQueryParams = Depends(get_resident_notice_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_list_notices(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident notices fetched", data)


@router.get("/resident/notices/pinned")
async def resident_pinned_notices(
    query: ResidentNoticeListQueryParams = Depends(get_resident_notice_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_list_notices(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id, view="pinned"
    )
    return success_response(200, "Resident pinned notices fetched", data)


@router.get("/resident/notices/unread")
async def resident_unread_notices(
    query: ResidentNoticeListQueryParams = Depends(get_resident_notice_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_list_notices(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id, view="unread"
    )
    return success_response(200, "Resident unread notices fetched", data)


@router.get("/resident/notices/archive")
async def resident_archived_notices(
    query: ResidentNoticeListQueryParams = Depends(get_resident_notice_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_list_notices(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id, view="archive"
    )
    return success_response(200, "Resident archived notices fetched", data)


@router.get("/resident/notices/{notice_id}")
async def resident_get_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_get_notice(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident notice fetched", data)


@router.post("/resident/notices/{notice_id}/read")
async def resident_mark_notice_read(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_mark_read(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice marked as read", data)


@router.post("/resident/notices/{notice_id}/acknowledge")
async def resident_acknowledge_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_acknowledge(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice acknowledged", data)


@router.get("/resident/notices/{notice_id}/attachments")
async def resident_notice_attachments(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_notice_service.resident_list_attachments(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident notice attachments fetched", data)
