"""Flat routes — /api/v1/flats."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.flat_list_query import get_flat_list_query
from Schemas.flat import FlatCreate, FlatListQueryParams, FlatUpdate
from Services import flat_service, occupancy_service, visit_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/flats", tags=["flats"])


@router.post("")
async def create_flat(
    body: FlatCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.create_flat(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Flat created successfully", data)


@router.get("")
async def list_flats(
    db: AsyncSession = Depends(get_db),
    query: FlatListQueryParams = Depends(get_flat_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.list_flats(db, query, actor_society_id=current.society_id)
    return success_response(200, "Flats fetched", data)


@router.get("/{flat_id}")
async def get_flat(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.get_flat(db, flat_id, actor_society_id=current.society_id)
    return success_response(200, "Flat fetched", data)


@router.patch("/{flat_id}")
async def update_flat(
    flat_id: UUID,
    body: FlatUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.update_flat(
        db,
        flat_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Flat updated successfully", data)


@router.post("/{flat_id}/deactivate")
async def deactivate_flat(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.set_flat_active(
        db,
        flat_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Flat deactivated"), data)


@router.post("/{flat_id}/activate")
async def activate_flat(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await flat_service.set_flat_active(
        db,
        flat_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Flat activated"), data)


@router.get("/{flat_id}/occupancies")
async def list_flat_occupancies(
    flat_id: UUID,
    current_only: bool = Query(True, alias="currentOnly"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.list_flat_occupancies(
        db,
        flat_id,
        actor_society_id=current.society_id,
        current_only=current_only,
    )
    return success_response(200, "Flat occupancies fetched", data)


@router.get("/{flat_id}/household")
async def get_flat_household(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await occupancy_service.get_flat_household(
        db, flat_id, actor_society_id=current.society_id
    )
    return success_response(200, "Flat household fetched", data)


@router.get("/{flat_id}/visits")
async def list_flat_visits(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await visit_service.list_flat_visits(db, flat_id, actor_society_id=current.society_id)
    return success_response(200, "Flat visits fetched", data)
