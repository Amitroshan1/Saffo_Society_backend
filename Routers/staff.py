"""Staff routes — /api/v1/staff."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.shift_list_query import get_attendance_list_query, get_shift_list_query
from Dependencies.staff_list_query import get_staff_list_query
from Schemas.shift import AttendanceListQueryParams, ShiftListQueryParams
from Schemas.staff import StaffCreate, StaffListQueryParams, StaffUpdate
from Services import attendance_service, shift_service, staff_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])


@router.post("")
async def create_staff(
    body: StaffCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.create_staff(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Staff created successfully", data)


@router.get("")
async def list_staff(
    db: AsyncSession = Depends(get_db),
    query: StaffListQueryParams = Depends(get_staff_list_query),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.list_staff(db, query, actor_society_id=current.society_id)
    return success_response(200, "Staff fetched", data)


@router.get("/me")
async def get_my_staff(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await staff_service.get_my_staff(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Staff profile fetched", data)


@router.get("/{staff_id}")
async def get_staff(
    staff_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.get_staff(db, staff_id, actor_society_id=current.society_id)
    return success_response(200, "Staff fetched", data)


@router.patch("/{staff_id}")
async def update_staff(
    staff_id: UUID,
    body: StaffUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.update_staff(
        db, staff_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Staff updated successfully", data)


@router.post("/{staff_id}/deactivate")
async def deactivate_staff(
    staff_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.set_staff_active(
        db, staff_id, active=False, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Staff deactivated"), data)


@router.post("/{staff_id}/activate")
async def activate_staff(
    staff_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await staff_service.set_staff_active(
        db, staff_id, active=True, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Staff activated"), data)


@router.get("/{staff_id}/shifts")
async def staff_shifts(
    staff_id: UUID,
    db: AsyncSession = Depends(get_db),
    query: ShiftListQueryParams = Depends(get_shift_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        if str(me["staff"]["id"]) != str(staff_id):
            from Utils.errors import ApiError

            raise ApiError(403, "Access denied. Required roles: admin")
    data = await shift_service.list_shifts(
        db, query, actor_society_id=current.society_id, force_staff_id=staff_id
    )
    return success_response(200, "Staff shifts fetched", data)


@router.get("/{staff_id}/attendance")
async def staff_attendance(
    staff_id: UUID,
    db: AsyncSession = Depends(get_db),
    query: AttendanceListQueryParams = Depends(get_attendance_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        if str(me["staff"]["id"]) != str(staff_id):
            from Utils.errors import ApiError

            raise ApiError(403, "Access denied. Required roles: admin")
    data = await attendance_service.list_attendance(
        db, query, actor_society_id=current.society_id, force_staff_id=staff_id
    )
    return success_response(200, "Staff attendance fetched", data)
