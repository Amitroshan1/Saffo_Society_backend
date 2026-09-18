"""Gate business logic."""

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
from Schemas.common import build_pagination_meta
from Schemas.gate import GateCreate, GateListQueryParams, GateOut, GateUpdate
from Services.staff_helpers import get_building_in_society, get_gate_in_society
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _gate_dict(gate: Gate, *, building_name: str | None = None) -> Dict[str, Any]:
    return GateOut.from_orm_gate(gate, building_name=building_name).model_dump(mode="json")


async def create_gate(
    db: AsyncSession,
    body: GateCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    building_name = None
    if body.buildingId:
        building = await get_building_in_society(db, body.buildingId, society_id)
        building_name = building.name

    gate = Gate(
        society_id=society_id,
        building_id=body.buildingId,
        code=body.code,
        name=body.name,
        gate_type=body.gateType,
        location_description=body.locationDescription,
        latitude=body.latitude,
        longitude=body.longitude,
        geofence_radius_meters=body.geofenceRadiusMeters or 50,
        sequence=body.sequence,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(gate, actor_id)
    db.add(gate)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Gate code already exists in this society") from exc
    await db.refresh(gate)
    publish_simple(
        "GATE_CREATED",
        society_id=society_id,
        entity_type="gate",
        entity_id=gate.id,
        actor_id=actor_id,
    )
    return {"gate": _gate_dict(gate, building_name=building_name)}


async def list_gates(
    db: AsyncSession,
    query: GateListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = ("name", "code", "sequence", "gate_type", "created_at", "is_active")
    builder = (
        ListQueryBuilder(Gate)
        .filter_eq("society_id", society_id)
        .filter_eq("building_id", query.building_id)
        .filter_eq("gate_type", query.gate_type)
        .search(query.search, "name", "code", "location_description")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="sequence", secondary="name")
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda g: g
    )
    building_ids = {g.building_id for g in items if g.building_id}
    buildings = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {b.id: b.name for b in r.scalars().all()}
    return {
        "gates": [
            _gate_dict(g, building_name=buildings.get(g.building_id) if g.building_id else None)
            for g in items
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_gate(
    db: AsyncSession, gate_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    gate = await get_gate_in_society(db, gate_id, society_id)
    building_name = None
    if gate.building_id:
        building = await get_building_in_society(db, gate.building_id, society_id)
        building_name = building.name
    return {"gate": _gate_dict(gate, building_name=building_name)}


async def update_gate(
    db: AsyncSession,
    gate_id: UUID,
    body: GateUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    gate = await get_gate_in_society(db, gate_id, society_id)
    data = body.model_dump(exclude_unset=True)
    if "buildingId" in data and data["buildingId"]:
        await get_building_in_society(db, data["buildingId"], society_id)
    field_map = {
        "name": "name",
        "gateType": "gate_type",
        "buildingId": "building_id",
        "locationDescription": "location_description",
        "latitude": "latitude",
        "longitude": "longitude",
        "geofenceRadiusMeters": "geofence_radius_meters",
        "sequence": "sequence",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(gate, orm_key, data[api_key])
    apply_update_audit(gate, actor_id)
    await db.commit()
    await db.refresh(gate)
    return await get_gate(db, gate.id, actor_society_id=society_id)


async def set_gate_active(
    db: AsyncSession,
    gate_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    gate = await get_gate_in_society(db, gate_id, society_id)
    if not active:
        open_shifts = await db.execute(
            select(Shift.id).where(
                Shift.gate_id == gate.id,
                Shift.society_id == society_id,
                Shift.status.in_(("scheduled", "active")),
            )
        )
        if open_shifts.scalar_one_or_none():
            raise ApiError(422, "Cannot deactivate gate with scheduled or active shifts")
    if active:
        soft_activate(gate, actor_id)
    else:
        soft_deactivate(gate, actor_id)
    await db.commit()
    await db.refresh(gate)
    data = await get_gate(db, gate.id, actor_society_id=society_id)
    data["message"] = "Gate activated" if active else "Gate deactivated"
    return data


async def gate_on_duty(
    db: AsyncSession, gate_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    from Services import shift_service

    society_id = _require_society_id(actor_society_id)
    await get_gate_in_society(db, gate_id, society_id)
    from Schemas.shift import ShiftListQueryParams

    query = ShiftListQueryParams(
        page=1,
        page_size=100,
        gate_id=gate_id,
        status="active",
        sort_by="scheduled_start",
        sort_order="asc",
    )
    data = await shift_service.list_shifts(db, query, actor_society_id=society_id)
    return {"onDuty": data["shifts"]}
