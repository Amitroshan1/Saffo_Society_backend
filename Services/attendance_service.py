"""Staff attendance business logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.gate import Gate
from Models.staff import Staff
from Models.staff_attendance import StaffAttendance
from Schemas.common import build_pagination_meta
from Schemas.shift import (
    AttendanceCheckIn,
    AttendanceCheckOut,
    AttendanceListQueryParams,
    AttendanceOut,
)
from Services.staff_helpers import (
    get_gate_in_society,
    get_shift_in_society,
    get_staff_for_user,
    get_staff_in_society,
    utcnow,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _att_dict(
    row: StaffAttendance, *, staff_name: str | None = None, gate_name: str | None = None
) -> Dict[str, Any]:
    return AttendanceOut.from_orm_attendance(
        row, staff_name=staff_name, gate_name=gate_name
    ).model_dump(mode="json")


async def _serialize(db: AsyncSession, row: StaffAttendance) -> Dict[str, Any]:
    staff_name = None
    gate_name = None
    r = await db.execute(select(Staff).where(Staff.id == row.staff_id))
    st = r.scalar_one_or_none()
    if st:
        staff_name = st.name
    if row.gate_id:
        g = await db.execute(select(Gate).where(Gate.id == row.gate_id))
        gate = g.scalar_one_or_none()
        gate_name = gate.name if gate else None
    return _att_dict(row, staff_name=staff_name, gate_name=gate_name)


async def check_in(
    db: AsyncSession,
    body: AttendanceCheckIn,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    staff = await get_staff_in_society(db, body.staffId, society_id)
    if not staff.is_active:
        raise ApiError(422, "Staff is inactive")
    if actor_role == "guard":
        linked = await get_staff_for_user(db, actor_id, society_id)
        if linked.id != staff.id:
            raise ApiError(403, "Access denied. Required roles: admin")

    open_att = await db.execute(
        select(StaffAttendance).where(
            StaffAttendance.staff_id == staff.id,
            StaffAttendance.status == "checked_in",
        )
    )
    if open_att.scalar_one_or_none():
        raise ApiError(409, "Staff already has an open attendance record")

    if body.shiftId:
        shift = await get_shift_in_society(db, body.shiftId, society_id)
        if shift.staff_id != staff.id:
            raise ApiError(422, "Shift does not belong to this staff member")
    if body.gateId:
        await get_gate_in_society(db, body.gateId, society_id)

    row = StaffAttendance(
        society_id=society_id,
        staff_id=staff.id,
        shift_id=body.shiftId,
        gate_id=body.gateId or staff.assigned_gate_id,
        status="checked_in",
        check_in_time=body.checkInTime or utcnow(),
        recorded_by=actor_id if actor_role == "admin" else None,
        notes=body.notes,
        metadata_json={},
        is_active=True,
        version=1,
    )
    apply_create_audit(row, actor_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    publish_simple(
        "STAFF_CHECKED_IN",
        society_id=society_id,
        entity_type="staff_attendance",
        entity_id=row.id,
        actor_id=actor_id,
        payload={"staffId": str(staff.id)},
    )
    return {"attendance": await _serialize(db, row)}


async def check_out(
    db: AsyncSession,
    attendance_id: UUID,
    body: AttendanceCheckOut,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    result = await db.execute(
        select(StaffAttendance).where(
            StaffAttendance.id == attendance_id,
            StaffAttendance.society_id == society_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Attendance not found")
    if actor_role == "guard":
        linked = await get_staff_for_user(db, actor_id, society_id)
        if linked.id != row.staff_id:
            raise ApiError(403, "Access denied. Required roles: admin")
    if row.status != "checked_in":
        raise ApiError(422, "Attendance is not checked in")
    checkout = body.checkOutTime or utcnow()
    if checkout < row.check_in_time:
        raise ApiError(422, "checkOutTime must be on or after checkInTime")
    row.check_out_time = checkout
    row.status = "checked_out"
    row.is_active = False
    if body.notes:
        row.notes = body.notes
    apply_update_audit(row, actor_id)
    await db.commit()
    await db.refresh(row)
    publish_simple(
        "STAFF_CHECKED_OUT",
        society_id=society_id,
        entity_type="staff_attendance",
        entity_id=row.id,
        actor_id=actor_id,
    )
    return {"attendance": await _serialize(db, row)}


async def void_attendance(
    db: AsyncSession,
    attendance_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    result = await db.execute(
        select(StaffAttendance).where(
            StaffAttendance.id == attendance_id,
            StaffAttendance.society_id == society_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Attendance not found")
    if row.status == "voided":
        raise ApiError(422, "Attendance already voided")
    row.status = "voided"
    row.is_active = False
    apply_update_audit(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {"attendance": await _serialize(db, row)}


async def list_attendance(
    db: AsyncSession,
    query: AttendanceListQueryParams,
    *,
    actor_society_id: UUID | None,
    force_staff_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(StaffAttendance).where(StaffAttendance.society_id == society_id)
    staff_filter = force_staff_id or query.staff_id
    if staff_filter:
        base = base.where(StaffAttendance.staff_id == staff_filter)
    if query.gate_id:
        base = base.where(StaffAttendance.gate_id == query.gate_id)
    if query.shift_id:
        base = base.where(StaffAttendance.shift_id == query.shift_id)
    if query.status:
        base = base.where(StaffAttendance.status == query.status)
    if query.is_active is not None:
        base = base.where(StaffAttendance.is_active == query.is_active)

    base = base.order_by(
        StaffAttendance.check_in_time.asc()
        if query.sort_order == "asc"
        else StaffAttendance.check_in_time.desc()
    )
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list(
        (
            await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
        ).scalars().all()
    )
    staff_ids = {r.staff_id for r in rows}
    gate_ids = {r.gate_id for r in rows if r.gate_id}
    staff = {}
    gates = {}
    if staff_ids:
        sr = await db.execute(select(Staff).where(Staff.id.in_(staff_ids)))
        staff = {s.id: s.name for s in sr.scalars().all()}
    if gate_ids:
        gr = await db.execute(select(Gate).where(Gate.id.in_(gate_ids)))
        gates = {g.id: g.name for g in gr.scalars().all()}
    return {
        "attendance": [
            _att_dict(
                r,
                staff_name=staff.get(r.staff_id),
                gate_name=gates.get(r.gate_id) if r.gate_id else None,
            )
            for r in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_attendance(
    db: AsyncSession, attendance_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    result = await db.execute(
        select(StaffAttendance).where(
            StaffAttendance.id == attendance_id,
            StaffAttendance.society_id == society_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Attendance not found")
    return {"attendance": await _serialize(db, row)}
