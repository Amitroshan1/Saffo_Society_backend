"""Resident routes — /api/v1/residents."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.resident_list_query import get_resident_list_query
from Schemas.resident import ResidentCreate, ResidentListQueryParams, ResidentUpdate
from Services import resident_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/residents", tags=["residents"])


@router.post("")
async def create_resident(
    body: ResidentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.create_resident(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Resident created successfully", data)


@router.get("")
async def list_residents(
    db: AsyncSession = Depends(get_db),
    query: ResidentListQueryParams = Depends(get_resident_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.list_residents(db, query, actor_society_id=current.society_id)
    return success_response(200, "Residents fetched", data)


@router.get("/{resident_id}")
async def get_resident(
    resident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.get_resident(
        db, resident_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident fetched", data)


@router.patch("/{resident_id}")
async def update_resident(
    resident_id: UUID,
    body: ResidentUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.update_resident(
        db,
        resident_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Resident updated successfully", data)


@router.post("/{resident_id}/deactivate")
async def deactivate_resident(
    resident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.set_resident_active(
        db,
        resident_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Resident deactivated"), data)


@router.post("/{resident_id}/activate")
async def activate_resident(
    resident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await resident_service.set_resident_active(
        db,
        resident_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Resident activated"), data)
