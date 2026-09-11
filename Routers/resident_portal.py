"""Resident portal routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.complaint_list_query import get_complaint_list_query
from Dependencies.visit_list_query import get_visit_list_query
from Schemas.complaint import ComplaintCommentCreate, ComplaintCreate, ComplaintListQueryParams, ComplaintStatusUpdate
from Schemas.resident_portal import ResidentVisitorApprovalRequest, ResidentVisitorInvitationCreate
from Schemas.visit import VisitListQueryParams
from Services import complaint_service, resident_portal_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/resident", tags=["resident-portal"])


@router.get("/dashboard")
async def resident_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.get_dashboard(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident dashboard fetched", data)


@router.get("/household")
async def resident_household(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.get_household(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident household fetched", data)


@router.get("/flat")
async def resident_flat(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.get_flat(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident flat fetched", data)


@router.get("/visitors")
async def resident_visitors(
    query: VisitListQueryParams = Depends(get_visit_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.get_visitors(
        db,
        query,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Resident visitors fetched", data)


@router.post("/visitor-invitations")
async def resident_create_invitation(
    body: ResidentVisitorInvitationCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.create_visitor_invitation(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Visitor invitation created", data)


@router.post("/visitor-approval")
async def resident_visitor_approval(
    body: ResidentVisitorApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_portal_service.visitor_approval_action(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, f"Visitor {body.action} action completed", data)


@router.post("/complaints")
async def resident_create_complaint(
    body: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await complaint_service.create_complaint(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Complaint created successfully", data)


@router.get("/complaints")
async def resident_list_complaints(
    query: ComplaintListQueryParams = Depends(get_complaint_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    from Services.complaint_helpers import resolve_resident_context

    resident, _ = await resolve_resident_context(
        db, actor_id=current.user_id, society_id=current.society_id
    )
    data = await complaint_service.list_complaints(
        db,
        query,
        actor_society_id=current.society_id,
        resident_id=resident.id,
    )
    return success_response(200, "Resident complaints fetched", data)


@router.get("/complaints/{complaint_id}")
async def resident_get_complaint(
    complaint_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    await complaint_service.assert_resident_owns_complaint(
        db,
        complaint_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    data = await complaint_service.get_complaint(
        db, complaint_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident complaint fetched", data)


@router.post("/complaints/{complaint_id}/comments")
async def resident_add_complaint_comment(
    complaint_id: UUID,
    body: ComplaintCommentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    await complaint_service.assert_resident_owns_complaint(
        db,
        complaint_id,
        actor_id=current.user_id,
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


@router.post("/complaints/{complaint_id}/close")
async def resident_close_complaint(
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    resident, _ = await complaint_service.assert_resident_owns_complaint(
        db,
        complaint_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    data = await complaint_service.close_complaint(
        db,
        complaint_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
        resident_id=resident.id,
    )
    return success_response(200, "Complaint closed", data)
