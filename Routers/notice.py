"""Notice & Announcement routes — /api/v1/notices (admin/finance)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.notice_list_query import get_notice_list_query
from Schemas.notice import (
    NoticeAttachmentIn,
    NoticeCancelRequest,
    NoticeCreate,
    NoticeListQueryParams,
    NoticePinRequest,
    NoticeTargetsReplace,
    NoticeUpdate,
)
from Services import notice_dashboard_service, notice_report_service, notice_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["notices"])
FINANCE_ROLES = ("admin", "finance")


# ---------------------------------------------------------------------------
# Admin / finance — notices
# ---------------------------------------------------------------------------


@router.post("/notices")
async def create_notice(
    body: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.create_notice(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id, actor_role=current.role
    )
    return success_response(201, "Notice created successfully", data)


@router.get("/notices")
async def list_notices(
    query: NoticeListQueryParams = Depends(get_notice_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.list_notices(db, query, actor_society_id=current.society_id)
    return success_response(200, "Notices fetched", data)


@router.get("/notices/dashboard")
async def notices_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_dashboard_service.get_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Notice dashboard fetched", data)


@router.get("/notices/reports/{report_key}")
async def notices_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
    notice_id: str | None = Query(None, alias="noticeId"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    data = await notice_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={"noticeId": notice_id, "from": from_date, "to": to_date},
    )
    return success_response(200, "Notice report fetched", data)


@router.post("/notices/process-due")
async def process_due_notices(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await notice_service.process_due_notices(
        db, actor_society_id=current.society_id, actor_id=current.user_id
    )
    return success_response(200, "Due notices processed", data)


@router.get("/notices/{notice_id}")
async def get_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.get_notice(db, notice_id, actor_society_id=current.society_id)
    return success_response(200, "Notice fetched", data)


@router.patch("/notices/{notice_id}")
async def update_notice(
    notice_id: UUID,
    body: NoticeUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.update_notice(
        db,
        notice_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Notice updated successfully", data)


@router.post("/notices/{notice_id}/publish")
async def publish_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.publish_notice(
        db,
        notice_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Notice published", data)


@router.post("/notices/{notice_id}/cancel")
async def cancel_notice(
    notice_id: UUID,
    body: NoticeCancelRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.cancel_notice(
        db,
        notice_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Notice cancelled", data)


@router.post("/notices/{notice_id}/archive")
async def archive_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await notice_service.archive_notice(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice archived", data)


@router.post("/notices/{notice_id}/pin")
async def pin_notice(
    notice_id: UUID,
    body: NoticePinRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await notice_service.pin_notice(
        db, notice_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice pinned", data)


@router.post("/notices/{notice_id}/unpin")
async def unpin_notice(
    notice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await notice_service.unpin_notice(
        db, notice_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice unpinned", data)


@router.put("/notices/{notice_id}/targets")
async def replace_notice_targets(
    notice_id: UUID,
    body: NoticeTargetsReplace,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.replace_targets(
        db,
        notice_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Notice targets updated", data)


@router.post("/notices/{notice_id}/attachments")
async def add_notice_attachment(
    notice_id: UUID,
    body: NoticeAttachmentIn,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.add_attachment(
        db,
        notice_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Notice attachment added", data)


@router.delete("/notices/{notice_id}/attachments/{attachment_id}")
async def remove_notice_attachment(
    notice_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await notice_service.remove_attachment(
        db, notice_id, attachment_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Notice attachment removed", data)


@router.get("/notices/{notice_id}/reads")
async def get_notice_reads(
    notice_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.get_reads(
        db, notice_id, actor_society_id=current.society_id, page=page, page_size=page_size
    )
    return success_response(200, "Notice reads fetched", data)


@router.get("/notices/{notice_id}/acknowledgements")
async def get_notice_acknowledgements(
    notice_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notice_service.get_acknowledgements(
        db, notice_id, actor_society_id=current.society_id, page=page, page_size=page_size
    )
    return success_response(200, "Notice acknowledgements fetched", data)
