"""Occupancy routes — /api/v1/occupancies."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.occupancy_list_query import get_occupancy_list_query
from Schemas.occupancy import (
    OccupancyCreate,
    OccupancyListQueryParams,
    OccupancyMoveOut,
    OccupancyUpdate,
)
from Services import occupancy_service, visit_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/occupancies", tags=["occupancies"])


@router.post("")
async def create_occupancy(
    body: OccupancyCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.create_occupancy(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Occupancy created (move-in)", data)


@router.get("")
async def list_occupancies(
    db: AsyncSession = Depends(get_db),
    query: OccupancyListQueryParams = Depends(get_occupancy_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.list_occupancies(db, query, actor_society_id=current.society_id)
    return success_response(200, "Occupancies fetched", data)


@router.get("/{occupancy_id}")
async def get_occupancy(
    occupancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.get_occupancy(
        db, occupancy_id, actor_society_id=current.society_id
    )
    return success_response(200, "Occupancy fetched", data)


@router.patch("/{occupancy_id}")
async def update_occupancy(
    occupancy_id: UUID,
    body: OccupancyUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.update_occupancy(
        db,
        occupancy_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Occupancy updated successfully", data)


@router.post("/{occupancy_id}/move-out")
async def move_out_occupancy(
    occupancy_id: UUID,
    body: OccupancyMoveOut,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.move_out_occupancy(
        db,
        occupancy_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Occupancy ended"), data)


@router.post("/{occupancy_id}/cancel")
async def cancel_occupancy(
    occupancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.cancel_occupancy(
        db,
        occupancy_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Occupancy cancelled"), data)


@router.get("/{occupancy_id}/visits")
async def list_occupancy_visits(
    occupancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.list_occupancy_visits(
        db, occupancy_id, actor_society_id=current.society_id
    )
    return success_response(200, "Occupancy visits fetched", data)
