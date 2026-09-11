"""Complaint routes — /api/v1/complaints (admin/staff)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.complaint_list_query import get_complaint_list_query
from Schemas.complaint import (
    ComplaintAssign,
    ComplaintCommentCreate,
    ComplaintCreate,
    ComplaintListQueryParams,
    ComplaintPriorityUpdate,
    ComplaintStatusUpdate,
    ComplaintUpdate,
)
from Services import complaint_service
from Services.complaint_helpers import get_complaint_in_society, get_staff_for_user
from Utils.errors import ApiError
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])


@router.post("")
async def create_complaint(
    body: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.create_complaint(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Complaint created successfully", data)


@router.get("")
async def list_complaints(
    db: AsyncSession = Depends(get_db),
    query: ComplaintListQueryParams = Depends(get_complaint_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    assigned_staff_id = None
    if current.role == "guard":
        staff = await get_staff_for_user(db, current.user_id, current.society_id)
        if not staff:
            from Schemas.common import build_pagination_meta

            return success_response(
                200,
                "Complaints fetched",
                {
                    "complaints": [],
                    "pagination": build_pagination_meta(query.page, query.page_size, 0),
                },
            )
        assigned_staff_id = staff.id
    data = await complaint_service.list_complaints(
        db,
        query,
        actor_society_id=current.society_id,
        assigned_staff_id=assigned_staff_id,
    )
    return success_response(200, "Complaints fetched", data)


@router.get("/dashboard")
async def complaints_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.dashboard_stats(db, actor_society_id=current.society_id)
    return success_response(200, "Complaint dashboard fetched", data)


@router.get("/{complaint_id}")
async def get_complaint(
    complaint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        complaint = await get_complaint_in_society(
            db, complaint_id, current.society_id
        )
        await complaint_service.assert_staff_assigned_or_admin(
            db,
            complaint,
            actor_id=current.user_id,
            actor_role=current.role,
            actor_society_id=current.society_id,
        )
    data = await complaint_service.get_complaint(
        db, complaint_id, actor_society_id=current.society_id
    )
    return success_response(200, "Complaint fetched", data)


@router.patch("/{complaint_id}")
async def update_complaint(
    complaint_id: UUID,
    body: ComplaintUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.update_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint updated successfully", data)


@router.post("/{complaint_id}/assign")
async def assign_complaint(
    complaint_id: UUID,
    body: ComplaintAssign,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.assign_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint assigned", data)


@router.post("/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: UUID,
    body: ComplaintStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        complaint = await get_complaint_in_society(
            db, complaint_id, current.society_id
        )
        await complaint_service.assert_staff_assigned_or_admin(
            db,
            complaint,
            actor_id=current.user_id,
            actor_role=current.role,
            actor_society_id=current.society_id,
        )
        if body.status in {"closed", "rejected", "reopened"}:
            raise ApiError(403, "Staff cannot change complaint to this status")
    data = await complaint_service.update_status(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint status updated", data)


@router.post("/{complaint_id}/priority")
async def update_complaint_priority(
    complaint_id: UUID,
    body: ComplaintPriorityUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.update_priority(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint priority updated", data)


@router.post("/{complaint_id}/comments")
async def add_complaint_comment(
    complaint_id: UUID,
    body: ComplaintCommentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        complaint = await get_complaint_in_society(
            db, complaint_id, current.society_id
        )
        await complaint_service.assert_staff_assigned_or_admin(
            db,
            complaint,
            actor_id=current.user_id,
            actor_role=current.role,
            actor_society_id=current.society_id,
        )
    data = await complaint_service.add_comment(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Comment added", data)


@router.post("/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        complaint = await get_complaint_in_society(
            db, complaint_id, current.society_id
        )
        await complaint_service.assert_staff_assigned_or_admin(
            db,
            complaint,
            actor_id=current.user_id,
            actor_role=current.role,
            actor_society_id=current.society_id,
        )
    data = await complaint_service.resolve_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint resolved", data)


@router.post("/{complaint_id}/reopen")
async def reopen_complaint(
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.reopen_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Complaint reopened", data)


@router.post("/{complaint_id}/close")
async def close_complaint(
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await complaint_service.close_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Complaint closed", data)
