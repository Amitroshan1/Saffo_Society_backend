"""Staff attendance routes — /api/v1/staff-attendance."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.shift_list_query import get_attendance_list_query
from Schemas.shift import AttendanceCheckIn, AttendanceCheckOut, AttendanceListQueryParams
from Services import attendance_service, staff_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/staff-attendance", tags=["staff-attendance"])


@router.post("/check-in")
async def check_in(
    body: AttendanceCheckIn,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await attendance_service.check_in(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Staff checked in", data)


@router.get("")
async def list_attendance(
    db: AsyncSession = Depends(get_db),
    query: AttendanceListQueryParams = Depends(get_attendance_list_query),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    force_staff_id = None
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        force_staff_id = UUID(me["staff"]["id"])
    data = await attendance_service.list_attendance(
        db, query, actor_society_id=current.society_id, force_staff_id=force_staff_id
    )
    return success_response(200, "Attendance fetched", data)


@router.get("/{attendance_id}")
async def get_attendance(
    attendance_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await attendance_service.get_attendance(
        db, attendance_id, actor_society_id=current.society_id
    )
    if current.role == "guard":
        me = await staff_service.get_my_staff(
            db, actor_id=current.user_id, actor_society_id=current.society_id
        )
        if data["attendance"]["staffId"] != me["staff"]["id"]:
            from Utils.errors import ApiError

            raise ApiError(404, "Attendance not found")
    return success_response(200, "Attendance fetched", data)


@router.post("/{attendance_id}/check-out")
async def check_out(
    attendance_id: UUID,
    body: AttendanceCheckOut,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin", "guard")),
):
    data = await attendance_service.check_out(
        db,
        attendance_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Staff checked out", data)


@router.post("/{attendance_id}/void")
async def void_attendance(
    attendance_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await attendance_service.void_attendance(
        db, attendance_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Attendance voided", data)
