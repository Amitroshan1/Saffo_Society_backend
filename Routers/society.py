"""Society routes — /api/v1/societies."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, get_current_user, require_roles
from Dependencies.list_query import get_list_query
from Schemas.common import ListQueryParams
from Schemas.society import SocietyCreate, SocietyUpdate
from Services import society_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/societies", tags=["societies"])


@router.post("")
async def create_society(
    body: SocietyCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await society_service.create_society(db, body, actor_id=current.user_id)
    return success_response(201, "Society created successfully", data)


@router.get("")
async def list_societies(
    db: AsyncSession = Depends(get_db),
    query: ListQueryParams = Depends(get_list_query),
    _: CurrentUser = Depends(require_roles("admin")),
):
    data = await society_service.list_societies(db, query)
    return success_response(200, "Societies fetched", data)


@router.get("/me")
async def get_my_society(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await society_service.get_my_society(db, current.society_id)
    return success_response(200, "Society fetched", data)


@router.get("/{society_id}")
async def get_society(
    society_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    if current.society_id and current.society_id != society_id:
        from Utils.errors import ApiError

        raise ApiError(404, "Society not found")
    data = await society_service.get_society(db, society_id)
    return success_response(200, "Society fetched", data)


@router.patch("/{society_id}")
async def update_society(
    society_id: UUID,
    body: SocietyUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await society_service.update_society(
        db,
        society_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Society updated successfully", data)


@router.post("/{society_id}/deactivate")
async def deactivate_society(
    society_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await society_service.set_society_active(
        db,
        society_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Society deactivated"), data)


@router.post("/{society_id}/activate")
async def activate_society(
    society_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await society_service.set_society_active(
        db,
        society_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Society activated"), data)
