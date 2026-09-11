"""Visit routes — /api/v1/visits."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.visit_list_query import get_visit_list_query
from Schemas.visit import (
    VisitCheckIn,
    VisitCheckOut,
    VisitCreate,
    VisitDecision,
    VisitListQueryParams,
    VisitUpdate,
)
from Services import visit_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/visits", tags=["visits"])


@router.post("")
async def create_visit(
    body: VisitCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.create_visit(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Visit created successfully", data)


@router.get("")
async def list_visits(
    db: AsyncSession = Depends(get_db),
    query: VisitListQueryParams = Depends(get_visit_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.list_visits(db, query, actor_society_id=current.society_id)
    return success_response(200, "Visits fetched", data)


@router.get("/{visit_id}")
async def get_visit(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.get_visit(db, visit_id, actor_society_id=current.society_id)
    return success_response(200, "Visit fetched", data)


@router.patch("/{visit_id}")
async def update_visit(
    visit_id: UUID,
    body: VisitUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.update_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit updated successfully", data)


@router.post("/{visit_id}/approve")
async def approve_visit(
    visit_id: UUID,
    body: VisitDecision,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await visit_service.approve_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit approved", data)


@router.post("/{visit_id}/reject")
async def reject_visit(
    visit_id: UUID,
    body: VisitDecision,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await visit_service.reject_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit rejected", data)


@router.post("/{visit_id}/check-in")
async def check_in_visit(
    visit_id: UUID,
    body: VisitCheckIn,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.check_in_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit checked in", data)


@router.post("/{visit_id}/check-out")
async def check_out_visit(
    visit_id: UUID,
    body: VisitCheckOut,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.check_out_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit checked out", data)


@router.post("/{visit_id}/cancel")
async def cancel_visit(
    visit_id: UUID,
    body: VisitDecision,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await visit_service.cancel_visit(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visit cancelled", data)
