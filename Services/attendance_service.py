"""Staff attendance business logic."""

from __future__ import annotations

from typing import Any, Dict, Optional
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
from Utils.geo import gate_has_coordinates, is_within_radius


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


def _location_payload(
    *,
    latitude: float,
    longitude: float,
    accuracy_meters: Optional[float],
    distance_meters: Optional[float],
    on_location: Optional[bool],
) -> Dict[str, Any]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "accuracyMeters": accuracy_meters,
        "distanceMeters": None if distance_meters is None else round(distance_meters, 2),
        "onLocation": on_location,
        "capturedAt": utcnow().isoformat(),
    }


async def _resolve_gate_for_check_in(
    db: AsyncSession,
    *,
    society_id: UUID,
    body: AttendanceCheckIn,
    staff: Staff,
    shift_gate_id: UUID | None,
) -> Gate | None:
    gate_id = body.gateId or shift_gate_id or staff.assigned_gate_id
    if not gate_id:
        return None
    return await get_gate_in_society(db, gate_id, society_id)


def _enforce_and_build_location(
    *,
    actor_role: str,
    gate: Gate | None,
    latitude: Optional[float],
    longitude: Optional[float],
    accuracy_meters: Optional[float],
    action: str,
) -> Dict[str, Any] | None:
    """
    Guard geofence rules (non-breaking for unconfigured gates):
    - Gate without lat/lng: skip enforcement (existing punch flows keep working).
    - Gate with lat/lng + guard: require client coords and enforce radius.
    - Admin: GPS optional; if provided with configured gate, store distance (no reject).
    """
    has_client_coords = latitude is not None and longitude is not None
    gate_configured = bool(gate and gate_has_coordinates(gate.latitude, gate.longitude))

    if actor_role == "guard" and gate_configured:
        if not has_client_coords:
            raise ApiError(422, f"Location is required for {action} at this gate")
        radius = gate.geofence_radius_meters or 120
        inside, distance = is_within_radius(
            latitude, longitude, gate.latitude, gate.longitude, radius
        )
        if not inside:
            raise ApiError(422, "You are outside the gate radius")
        return _location_payload(
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            distance_meters=distance,
            on_location=True,
        )

    if has_client_coords:
        distance = None
        on_location = None
        if gate_configured:
            radius = gate.geofence_radius_meters or 120
            on_location, distance = is_within_radius(
                latitude, longitude, gate.latitude, gate.longitude, radius
            )
        return _location_payload(
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            distance_meters=distance,
            on_location=on_location,
        )

    return None


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

    shift_gate_id = None
    if body.shiftId:
        shift = await get_shift_in_society(db, body.shiftId, society_id)
        if shift.staff_id != staff.id:
            raise ApiError(422, "Shift does not belong to this staff member")
        shift_gate_id = shift.gate_id

    gate = await _resolve_gate_for_check_in(
        db,
        society_id=society_id,
        body=body,
        staff=staff,
        shift_gate_id=shift_gate_id,
    )

    location_meta = _enforce_and_build_location(
        actor_role=actor_role,
        gate=gate,
        latitude=body.latitude,
        longitude=body.longitude,
        accuracy_meters=body.accuracyMeters,
        action="check-in",
    )
    metadata: Dict[str, Any] = {}
    if location_meta:
        metadata["checkInLocation"] = location_meta

    row = StaffAttendance(
        society_id=society_id,
        staff_id=staff.id,
        shift_id=body.shiftId,
        gate_id=gate.id if gate else None,
        status="checked_in",
        check_in_time=body.checkInTime or utcnow(),
        recorded_by=actor_id if actor_role == "admin" else None,
        notes=body.notes,
        metadata_json=metadata,
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

    gate = None
    if row.gate_id:
        gate = await get_gate_in_society(db, row.gate_id, society_id)

    location_meta = _enforce_and_build_location(
        actor_role=actor_role,
        gate=gate,
        latitude=body.latitude,
        longitude=body.longitude,
        accuracy_meters=body.accuracyMeters,
        action="check-out",
    )
    meta = dict(row.metadata_json or {})
    if location_meta:
        meta["checkOutLocation"] = location_meta
        row.metadata_json = meta

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
