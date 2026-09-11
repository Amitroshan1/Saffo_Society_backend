"""Shift routes — /api/v1/shifts."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.shift_list_query import get_shift_list_query
from Schemas.shift import ShiftCreate, ShiftListQueryParams, ShiftNotes, ShiftUpdate
from Services import shift_service, staff_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/shifts", tags=["shifts"])


@router.get("/today")
async def today_shifts(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await shift_service.list_today_shifts(db, actor_society_id=current.society_id)
    return success_response(200, "Today shifts fetched", data)


@router.post("")
async def create_shift(
    body: ShiftCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await shift_service.create_shift(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Shift scheduled successfully", data)


@router.get("")
async def list_shifts(
    db: AsyncSession = Depends(get_db),
    query: ShiftListQueryParams = Depends(get_shift_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    force_staff_id = None
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        force_staff_id = UUID(me["staff"]["id"])
    data = await shift_service.list_shifts(
        db, query, actor_society_id=current.society_id, force_staff_id=force_staff_id
    )
    return success_response(200, "Shifts fetched", data)


@router.get("/{shift_id}")
async def get_shift(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await shift_service.get_shift(db, shift_id, actor_society_id=current.society_id)
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        if data["shift"]["staffId"] != me["staff"]["id"]:
            from Utils.errors import ApiError

            raise ApiError(404, "Shift not found")
    return success_response(200, "Shift fetched", data)


@router.patch("/{shift_id}")
async def update_shift(
    shift_id: UUID,
    body: ShiftUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await shift_service.update_shift(
        db, shift_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Shift updated successfully", data)


@router.post("/{shift_id}/start")
async def start_shift(
    shift_id: UUID,
    body: ShiftNotes,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await shift_service.start_shift(
        db,
        shift_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Shift started", data)


@router.post("/{shift_id}/complete")
async def complete_shift(
    shift_id: UUID,
    body: ShiftNotes,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await shift_service.complete_shift(
        db,
        shift_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Shift completed", data)


@router.post("/{shift_id}/cancel")
async def cancel_shift(
    shift_id: UUID,
    body: ShiftNotes,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await shift_service.cancel_shift(
        db, shift_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Shift cancelled", data)


@router.post("/{shift_id}/no-show")
async def mark_no_show(
    shift_id: UUID,
    body: ShiftNotes,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await shift_service.mark_no_show(
        db, shift_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Shift marked no-show", data)
