"""Shift business logic."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.gate import Gate
from Models.shift import Shift
from Models.staff import Staff
from Schemas.common import build_pagination_meta
from Schemas.shift import ShiftCreate, ShiftListQueryParams, ShiftNotes, ShiftOut, ShiftUpdate
from Services.staff_helpers import (
    TERMINAL_SHIFT_STATUSES,
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


def _shift_dict(
    shift: Shift,
    *,
    staff_name: str | None = None,
    staff_code: str | None = None,
    gate_name: str | None = None,
) -> Dict[str, Any]:
    return ShiftOut.from_orm_shift(
        shift, staff_name=staff_name, staff_code=staff_code, gate_name=gate_name
    ).model_dump(mode="json")


async def _load_maps(db: AsyncSession, shifts: list[Shift]) -> tuple[dict, dict]:
    staff_ids = {s.staff_id for s in shifts}
    gate_ids = {s.gate_id for s in shifts if s.gate_id}
    staff = {}
    if staff_ids:
        r = await db.execute(select(Staff).where(Staff.id.in_(staff_ids)))
        staff = {x.id: x for x in r.scalars().all()}
    gates = {}
    if gate_ids:
        r = await db.execute(select(Gate).where(Gate.id.in_(gate_ids)))
        gates = {x.id: x for x in r.scalars().all()}
    return staff, gates


async def _serialize(db: AsyncSession, shift: Shift) -> Dict[str, Any]:
    staff, gates = await _load_maps(db, [shift])
    st = staff.get(shift.staff_id)
    gt = gates.get(shift.gate_id) if shift.gate_id else None
    return _shift_dict(
        shift,
        staff_name=st.name if st else None,
        staff_code=st.code if st else None,
        gate_name=gt.name if gt else None,
    )


async def create_shift(
    db: AsyncSession,
    body: ShiftCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    if body.scheduledEnd <= body.scheduledStart:
        raise ApiError(422, "scheduledEnd must be after scheduledStart")
    staff = await get_staff_in_society(db, body.staffId, society_id)
    if not staff.is_active:
        raise ApiError(422, "Staff is inactive")
    building_id = staff.assigned_building_id
    if body.gateId:
        gate = await get_gate_in_society(db, body.gateId, society_id)
        if not gate.is_active:
            raise ApiError(422, "Gate is inactive")
        building_id = gate.building_id or building_id

    # Overlap detection for scheduled/active
    overlap = await db.execute(
        select(Shift).where(
            Shift.staff_id == staff.id,
            Shift.status.in_(("scheduled", "active")),
            Shift.scheduled_start < body.scheduledEnd,
            Shift.scheduled_end > body.scheduledStart,
        )
    )
    if overlap.scalar_one_or_none():
        raise ApiError(409, "Overlapping shift already exists for this staff")

    shift = Shift(
        society_id=society_id,
        staff_id=staff.id,
        gate_id=body.gateId,
        building_id=building_id,
        shift_date=body.shiftDate,
        shift_type=body.shiftType,
        scheduled_start=body.scheduledStart,
        scheduled_end=body.scheduledEnd,
        status="scheduled",
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(shift, actor_id)
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    publish_simple(
        "SHIFT_SCHEDULED",
        society_id=society_id,
        entity_type="shift",
        entity_id=shift.id,
        actor_id=actor_id,
        payload={
            "staffId": str(shift.staff_id),
            "shift_type": shift.shift_type,
            "shift_date": shift.shift_date.isoformat() if shift.shift_date else "",
        },
    )
    return {"shift": await _serialize(db, shift)}


async def list_shifts(
    db: AsyncSession,
    query: ShiftListQueryParams,
    *,
    actor_society_id: UUID | None,
    force_staff_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(Shift).where(Shift.society_id == society_id)
    staff_filter = force_staff_id or query.staff_id
    if staff_filter:
        base = base.where(Shift.staff_id == staff_filter)
    if query.gate_id:
        base = base.where(Shift.gate_id == query.gate_id)
    if query.building_id:
        base = base.where(Shift.building_id == query.building_id)
    if query.status:
        base = base.where(Shift.status == query.status)
    if query.shift_type:
        base = base.where(Shift.shift_type == query.shift_type)
    if query.shift_date:
        base = base.where(Shift.shift_date == query.shift_date)
    if query.from_date:
        base = base.where(Shift.shift_date >= query.from_date)
    if query.to_date:
        base = base.where(Shift.shift_date <= query.to_date)
    if query.is_active is not None:
        base = base.where(Shift.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        staff_ids = select(Staff.id).where(
            Staff.society_id == society_id,
            or_(Staff.name.ilike(term), Staff.code.ilike(term)),
        )
        base = base.where(Shift.staff_id.in_(staff_ids))

    allowed = ("scheduled_start", "shift_date", "status", "created_at")
    sort_field = query.sort_by if query.sort_by in allowed else "scheduled_start"
    sort_col = getattr(Shift, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list(
        (
            await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
        ).scalars().all()
    )
    staff, gates = await _load_maps(db, rows)
    return {
        "shifts": [
            _shift_dict(
                s,
                staff_name=staff[s.staff_id].name if s.staff_id in staff else None,
                staff_code=staff[s.staff_id].code if s.staff_id in staff else None,
                gate_name=gates[s.gate_id].name if s.gate_id and s.gate_id in gates else None,
            )
            for s in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_shift(
    db: AsyncSession, shift_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    return {"shift": await _serialize(db, shift)}


async def update_shift(
    db: AsyncSession,
    shift_id: UUID,
    body: ShiftUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    if shift.status != "scheduled":
        raise ApiError(422, "Only scheduled shifts can be updated")
    data = body.model_dump(exclude_unset=True)
    start = data.get("scheduledStart", shift.scheduled_start)
    end = data.get("scheduledEnd", shift.scheduled_end)
    if end <= start:
        raise ApiError(422, "scheduledEnd must be after scheduledStart")
    if data.get("gateId"):
        gate = await get_gate_in_society(db, data["gateId"], society_id)
        shift.building_id = gate.building_id or shift.building_id
    field_map = {
        "gateId": "gate_id",
        "shiftType": "shift_type",
        "scheduledStart": "scheduled_start",
        "scheduledEnd": "scheduled_end",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(shift, orm_key, data[api_key])
    apply_update_audit(shift, actor_id)
    await db.commit()
    await db.refresh(shift)
    return {"shift": await _serialize(db, shift)}


async def start_shift(
    db: AsyncSession,
    shift_id: UUID,
    body: ShiftNotes,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    if actor_role == "guard":
        staff = await get_staff_for_user(db, actor_id, society_id)
        if shift.staff_id != staff.id:
            raise ApiError(403, "Access denied. Required roles: admin")
    if shift.status != "scheduled":
        raise ApiError(422, "Only scheduled shifts can be started")
    shift.status = "active"
    shift.actual_start = utcnow()
    if body.notes:
        shift.notes = body.notes
    apply_update_audit(shift, actor_id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Staff already has an active shift") from exc
    await db.refresh(shift)
    publish_simple(
        "SHIFT_STARTED",
        society_id=society_id,
        entity_type="shift",
        entity_id=shift.id,
        actor_id=actor_id,
    )
    return {"shift": await _serialize(db, shift)}


async def complete_shift(
    db: AsyncSession,
    shift_id: UUID,
    body: ShiftNotes,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    if actor_role == "guard":
        staff = await get_staff_for_user(db, actor_id, society_id)
        if shift.staff_id != staff.id:
            raise ApiError(403, "Access denied. Required roles: admin")
    if shift.status != "active":
        raise ApiError(422, "Only active shifts can be completed")
    shift.status = "completed"
    shift.actual_end = utcnow()
    shift.is_active = False
    if body.notes:
        shift.notes = body.notes
    apply_update_audit(shift, actor_id)
    await db.commit()
    await db.refresh(shift)
    publish_simple(
        "SHIFT_COMPLETED",
        society_id=society_id,
        entity_type="shift",
        entity_id=shift.id,
        actor_id=actor_id,
    )
    return {"shift": await _serialize(db, shift)}


async def cancel_shift(
    db: AsyncSession,
    shift_id: UUID,
    body: ShiftNotes,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    if shift.status in TERMINAL_SHIFT_STATUSES:
        raise ApiError(422, f"Shift is {shift.status} and cannot be cancelled")
    shift.status = "cancelled"
    shift.is_active = False
    if body.notes:
        shift.notes = body.notes
    apply_update_audit(shift, actor_id)
    await db.commit()
    await db.refresh(shift)
    return {"shift": await _serialize(db, shift)}


async def mark_no_show(
    db: AsyncSession,
    shift_id: UUID,
    body: ShiftNotes,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    shift = await get_shift_in_society(db, shift_id, society_id)
    if shift.status != "scheduled":
        raise ApiError(422, "Only scheduled shifts can be marked no-show")
    shift.status = "no_show"
    shift.is_active = False
    if body.notes:
        shift.notes = body.notes
    apply_update_audit(shift, actor_id)
    await db.commit()
    await db.refresh(shift)
    publish_simple(
        "SHIFT_NO_SHOW",
        society_id=society_id,
        entity_type="shift",
        entity_id=shift.id,
        actor_id=actor_id,
    )
    return {"shift": await _serialize(db, shift)}


async def list_today_shifts(
    db: AsyncSession, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    query = ShiftListQueryParams(
        page=1,
        page_size=100,
        shift_date=date.today(),
        sort_by="scheduled_start",
        sort_order="asc",
    )
    return await list_shifts(db, query, actor_society_id=actor_society_id)


async def gate_ops_dashboard(
    db: AsyncSession, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    today = date.today()
    gates_r = await db.execute(
        select(Gate).where(Gate.society_id == society_id, Gate.is_active.is_(True)).order_by(Gate.sequence)
    )
    gates = list(gates_r.scalars().all())
    active_r = await db.execute(
        select(Shift).where(
            Shift.society_id == society_id,
            Shift.status == "active",
            Shift.shift_date == today,
        )
    )
    active = list(active_r.scalars().all())
    staff, gate_map = await _load_maps(db, active)
    on_duty = [
        _shift_dict(
            s,
            staff_name=staff[s.staff_id].name if s.staff_id in staff else None,
            staff_code=staff[s.staff_id].code if s.staff_id in staff else None,
            gate_name=gate_map[s.gate_id].name if s.gate_id and s.gate_id in gate_map else None,
        )
        for s in active
    ]
    today_data = await list_today_shifts(db, actor_society_id=society_id)
    return {
        "gates": [
            {"id": str(g.id), "code": g.code, "name": g.name, "gateType": g.gate_type}
            for g in gates
        ],
        "onDuty": on_duty,
        "todayShifts": today_data["shifts"],
    }


async def mark_stale_no_shows(db: AsyncSession, society_id: UUID, *, actor_id: UUID) -> int:
    """Scheduler handler: mark overdue scheduled shifts as no_show."""
    now = utcnow()
    result = await db.execute(
        select(Shift).where(
            Shift.society_id == society_id,
            Shift.status == "scheduled",
            Shift.scheduled_end < now,
        )
    )
    count = 0
    for shift in result.scalars().all():
        shift.status = "no_show"
        shift.is_active = False
        apply_update_audit(shift, actor_id)
        count += 1
        publish_simple(
            "SHIFT_NO_SHOW",
            society_id=society_id,
            entity_type="shift",
            entity_id=shift.id,
            actor_id=actor_id,
        )
    if count:
        await db.commit()
    return count
