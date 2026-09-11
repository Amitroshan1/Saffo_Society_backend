"""Shift and attendance list query dependencies."""

from datetime import date
from uuid import UUID

from fastapi import Query

from Schemas.shift import AttendanceListQueryParams, ShiftListQueryParams


def get_shift_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("scheduled_start", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    # Param names must not match nested path vars like `{staff_id}` / `{gate_id}`.
    filter_staff_id: UUID | None = Query(None, alias="staffId"),
    filter_gate_id: UUID | None = Query(None, alias="gateId"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    status: str | None = Query(None),
    shift_type: str | None = Query(None, alias="shiftType"),
    shift_date: date | None = Query(None, alias="shiftDate"),
    from_date: date | None = Query(None, alias="fromDate"),
    to_date: date | None = Query(None, alias="toDate"),
) -> ShiftListQueryParams:
    return ShiftListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        staff_id=filter_staff_id,
        gate_id=filter_gate_id,
        building_id=building_id,
        status=status.strip().lower() if status else None,
        shift_type=shift_type.strip().lower() if shift_type else None,
        shift_date=shift_date,
        from_date=from_date,
        to_date=to_date,
    )


def get_attendance_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("check_in_time", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    filter_staff_id: UUID | None = Query(None, alias="staffId"),
    filter_gate_id: UUID | None = Query(None, alias="gateId"),
    filter_shift_id: UUID | None = Query(None, alias="shiftId"),
    status: str | None = Query(None),
) -> AttendanceListQueryParams:
    return AttendanceListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        staff_id=filter_staff_id,
        gate_id=filter_gate_id,
        shift_id=filter_shift_id,
        status=status.strip().lower() if status else None,
    )
