"""Visitor routes — /api/v1/visitors."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.visitor_list_query import get_visitor_list_query
from Schemas.visitor import VisitorCreate, VisitorListQueryParams, VisitorUpdate
from Services import visitor_service, visit_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/visitors", tags=["visitors"])


@router.post("")
async def create_visitor(
    body: VisitorCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visitor_service.create_visitor(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Visitor created successfully", data)


@router.get("")
async def list_visitors(
    db: AsyncSession = Depends(get_db),
    query: VisitorListQueryParams = Depends(get_visitor_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visitor_service.list_visitors(db, query, actor_society_id=current.society_id)
    return success_response(200, "Visitors fetched", data)


@router.get("/{visitor_id}")
async def get_visitor(
    visitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visitor_service.get_visitor(db, visitor_id, actor_society_id=current.society_id)
    return success_response(200, "Visitor fetched", data)


@router.patch("/{visitor_id}")
async def update_visitor(
    visitor_id: UUID,
    body: VisitorUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visitor_service.update_visitor(
        db,
        visitor_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visitor updated successfully", data)


@router.post("/{visitor_id}/deactivate")
async def deactivate_visitor(
    visitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await visitor_service.set_visitor_active(
        db,
        visitor_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Visitor deactivated"), data)


@router.post("/{visitor_id}/activate")
async def activate_visitor(
    visitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await visitor_service.set_visitor_active(
        db,
        visitor_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Visitor activated"), data)


@router.get("/{visitor_id}/history")
async def visitor_history(
    visitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.visitor_history(db, visitor_id, actor_society_id=current.society_id)
    return success_response(200, "Visitor history fetched", data)
