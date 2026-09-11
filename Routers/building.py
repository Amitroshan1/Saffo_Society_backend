"""Building routes — /api/v1/buildings."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.list_query import get_list_query
from Schemas.building import BuildingCreate, BuildingUpdate
from Schemas.common import ListQueryParams
from Services import building_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/buildings", tags=["buildings"])


@router.post("")
async def create_building(
    body: BuildingCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.create_building(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Building created successfully", data)


@router.get("")
async def list_buildings(
    db: AsyncSession = Depends(get_db),
    query: ListQueryParams = Depends(get_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.list_buildings(
        db,
        query,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Buildings fetched", data)


@router.get("/{building_id}")
async def get_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.get_building(
        db,
        building_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Building fetched", data)


@router.patch("/{building_id}")
async def update_building(
    building_id: UUID,
    body: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.update_building(
        db,
        building_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Building updated successfully", data)


@router.post("/{building_id}/deactivate")
async def deactivate_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.set_building_active(
        db,
        building_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Building deactivated"), data)


@router.post("/{building_id}/activate")
async def activate_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await building_service.set_building_active(
        db,
        building_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Building activated"), data)
