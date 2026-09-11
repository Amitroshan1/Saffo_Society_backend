"""Wing routes — /api/v1/wings."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.wing_list_query import get_wing_list_query
from Schemas.wing import WingCreate, WingListQueryParams, WingUpdate
from Services import wing_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/wings", tags=["wings"])


@router.post("")
async def create_wing(
    body: WingCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.create_wing(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(201, "Wing created successfully", data)


@router.get("")
async def list_wings(
    db: AsyncSession = Depends(get_db),
    query: WingListQueryParams = Depends(get_wing_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.list_wings(db, query, actor_society_id=current.society_id)
    return success_response(200, "Wings fetched", data)


@router.get("/{wing_id}")
async def get_wing(
    wing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.get_wing(db, wing_id, actor_society_id=current.society_id)
    return success_response(200, "Wing fetched", data)


@router.patch("/{wing_id}")
async def update_wing(
    wing_id: UUID,
    body: WingUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.update_wing(
        db,
        wing_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Wing updated successfully", data)


@router.post("/{wing_id}/deactivate")
async def deactivate_wing(
    wing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.set_wing_active(
        db,
        wing_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Wing deactivated"), data)


@router.post("/{wing_id}/activate")
async def activate_wing(
    wing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await wing_service.set_wing_active(
        db,
        wing_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Wing activated"), data)
