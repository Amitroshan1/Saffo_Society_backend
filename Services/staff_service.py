"""Staff business logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.building import Building
from Models.gate import Gate
from Models.shift import Shift
from Models.staff import Staff
from Models.staff_attendance import StaffAttendance
from Schemas.common import build_pagination_meta
from Schemas.staff import StaffCreate, StaffListQueryParams, StaffOut, StaffUpdate
from Services.staff_helpers import (
    ensure_user_linkable_for_staff,
    get_building_in_society,
    get_gate_in_society,
    get_staff_for_user,
    get_staff_in_society,
    next_staff_code,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _staff_dict(
    staff: Staff, *, building_name: str | None = None, gate_name: str | None = None
) -> Dict[str, Any]:
    return StaffOut.from_orm_staff(
        staff, building_name=building_name, gate_name=gate_name
    ).model_dump(mode="json")


async def _enrich(db: AsyncSession, staff: Staff) -> Dict[str, Any]:
    building_name = None
    gate_name = None
    if staff.assigned_building_id:
        r = await db.execute(select(Building).where(Building.id == staff.assigned_building_id))
        b = r.scalar_one_or_none()
        building_name = b.name if b else None
    if staff.assigned_gate_id:
        r = await db.execute(select(Gate).where(Gate.id == staff.assigned_gate_id))
        g = r.scalar_one_or_none()
        gate_name = g.name if g else None
    return _staff_dict(staff, building_name=building_name, gate_name=gate_name)


async def create_staff(
    db: AsyncSession,
    body: StaffCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    if body.joiningDate and body.leavingDate and body.leavingDate < body.joiningDate:
        raise ApiError(422, "leavingDate must be on or after joiningDate")
    if body.userId:
        await ensure_user_linkable_for_staff(db, body.userId, society_id)
    if body.assignedBuildingId:
        await get_building_in_society(db, body.assignedBuildingId, society_id)
    if body.assignedGateId:
        await get_gate_in_society(db, body.assignedGateId, society_id)

    code = await next_staff_code(db, society_id)
    staff = Staff(
        society_id=society_id,
        user_id=body.userId,
        code=code,
        name=body.name,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        photo_url=body.photoUrl,
        staff_role=body.staffRole,
        department=body.department,
        employment_type=body.employmentType,
        assigned_building_id=body.assignedBuildingId,
        assigned_gate_id=body.assignedGateId,
        joining_date=body.joiningDate,
        leaving_date=body.leavingDate,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(staff, actor_id)
    db.add(staff)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Staff code or user link conflict") from exc
    await db.refresh(staff)
    publish_simple(
        "STAFF_CREATED",
        society_id=society_id,
        entity_type="staff",
        entity_id=staff.id,
        actor_id=actor_id,
        payload={"code": staff.code},
    )
    return {"staff": await _enrich(db, staff)}


async def list_staff(
    db: AsyncSession,
    query: StaffListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = ("name", "code", "staff_role", "created_at", "is_active")
    builder = (
        ListQueryBuilder(Staff)
        .filter_eq("society_id", society_id)
        .filter_eq("staff_role", query.staff_role)
        .filter_eq("employment_type", query.employment_type)
        .filter_eq("assigned_gate_id", query.assigned_gate_id)
        .filter_eq("assigned_building_id", query.assigned_building_id)
        .search(query.search, "name", "phone", "email", "code")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="name")
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda s: s
    )
    building_ids = {s.assigned_building_id for s in items if s.assigned_building_id}
    gate_ids = {s.assigned_gate_id for s in items if s.assigned_gate_id}
    buildings = {}
    gates = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {b.id: b.name for b in r.scalars().all()}
    if gate_ids:
        r = await db.execute(select(Gate).where(Gate.id.in_(gate_ids)))
        gates = {g.id: g.name for g in r.scalars().all()}
    return {
        "staff": [
            _staff_dict(
                s,
                building_name=buildings.get(s.assigned_building_id) if s.assigned_building_id else None,
                gate_name=gates.get(s.assigned_gate_id) if s.assigned_gate_id else None,
            )
            for s in items
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_staff(
    db: AsyncSession, staff_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    staff = await get_staff_in_society(db, staff_id, society_id)
    return {"staff": await _enrich(db, staff)}


async def get_my_staff(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    staff = await get_staff_for_user(db, actor_id, society_id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        staff = await get_staff_for_user(db, actor_id, society_id)
        await db.commit()
    await db.refresh(staff)
    return {"staff": await _enrich(db, staff)}


async def update_staff(
    db: AsyncSession,
    staff_id: UUID,
    body: StaffUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    staff = await get_staff_in_society(db, staff_id, society_id)
    data = body.model_dump(exclude_unset=True)
    joining = data.get("joiningDate", staff.joining_date)
    leaving = data.get("leavingDate", staff.leaving_date)
    if joining and leaving and leaving < joining:
        raise ApiError(422, "leavingDate must be on or after joiningDate")
    if "userId" in data and data["userId"]:
        await ensure_user_linkable_for_staff(
            db, data["userId"], society_id, except_staff_id=staff.id
        )
    if data.get("assignedBuildingId"):
        await get_building_in_society(db, data["assignedBuildingId"], society_id)
    if data.get("assignedGateId"):
        await get_gate_in_society(db, data["assignedGateId"], society_id)

    field_map = {
        "name": "name",
        "phone": "phone",
        "email": "email",
        "photoUrl": "photo_url",
        "staffRole": "staff_role",
        "department": "department",
        "employmentType": "employment_type",
        "userId": "user_id",
        "assignedBuildingId": "assigned_building_id",
        "assignedGateId": "assigned_gate_id",
        "joiningDate": "joining_date",
        "leavingDate": "leaving_date",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            val = data[api_key]
            if api_key == "email" and val is not None:
                val = str(val)
            setattr(staff, orm_key, val)
    apply_update_audit(staff, actor_id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "User is already linked to another staff member") from exc
    await db.refresh(staff)
    return {"staff": await _enrich(db, staff)}


async def set_staff_active(
    db: AsyncSession,
    staff_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    staff = await get_staff_in_society(db, staff_id, society_id)
    if not active:
        active_shift = await db.execute(
            select(Shift.id).where(
                Shift.staff_id == staff.id,
                Shift.status == "active",
            )
        )
        if active_shift.scalar_one_or_none():
            raise ApiError(422, "Cannot deactivate staff with an active shift")
        open_att = await db.execute(
            select(StaffAttendance.id).where(
                StaffAttendance.staff_id == staff.id,
                StaffAttendance.status == "checked_in",
            )
        )
        if open_att.scalar_one_or_none():
            raise ApiError(422, "Cannot deactivate staff with open attendance")
    if active:
        soft_activate(staff, actor_id)
    else:
        soft_deactivate(staff, actor_id)
        publish_simple(
            "STAFF_DEACTIVATED",
            society_id=society_id,
            entity_type="staff",
            entity_id=staff.id,
            actor_id=actor_id,
        )
    await db.commit()
    await db.refresh(staff)
    return {
        "staff": await _enrich(db, staff),
        "message": "Staff activated" if active else "Staff deactivated",
    }
