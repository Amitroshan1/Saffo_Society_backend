"""Wing business logic."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.wing import WingCreate, WingListQueryParams, WingOut, WingUpdate
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate
from Utils.validation_helpers import normalize_code, require_non_blank


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _wing_dict(
    wing: Wing,
    *,
    building_name: Optional[str] = None,
    building_code: Optional[str] = None,
) -> Dict[str, Any]:
    return WingOut.from_orm_wing(
        wing,
        building_name=building_name,
        building_code=building_code,
    ).model_dump(mode="json")


async def _load_buildings_map(
    db: AsyncSession, building_ids: set[UUID]
) -> Dict[UUID, Building]:
    if not building_ids:
        return {}
    result = await db.execute(select(Building).where(Building.id.in_(building_ids)))
    return {b.id: b for b in result.scalars().all()}


async def _get_building_in_society(
    db: AsyncSession, building_id: UUID, society_id: UUID
) -> Building:
    result = await db.execute(
        select(Building).where(Building.id == building_id, Building.society_id == society_id)
    )
    building = result.scalar_one_or_none()
    if not building:
        raise ApiError(404, "Building not found")
    return building


async def create_wing(
    db: AsyncSession,
    body: WingCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    building = await _get_building_in_society(db, body.buildingId, society_id)
    code = normalize_code(body.code)

    existing = await db.execute(
        select(Wing).where(Wing.building_id == building.id, Wing.code == code)
    )
    if existing.scalar_one_or_none():
        raise ApiError(409, "Wing code already exists in this building")

    wing = Wing(
        society_id=society_id,
        building_id=building.id,
        name=require_non_blank(body.name, "name"),
        display_name=body.displayName or body.name,
        code=code,
        short_code=body.shortCode,
        description=body.description,
        wing_type=body.wingType,
        status=body.status,
        metadata_json=body.metadata,
        sequence=body.sequence,
        color=body.color,
        total_floors=body.totalFloors,
        total_flats=body.totalFlats,
        elevator_count=body.elevatorCount,
        emergency_stair_count=body.emergencyStairCount,
        capacity=body.capacity,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(wing, actor_id)
    db.add(wing)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Wing code already exists in this building") from exc
    await db.refresh(wing)
    return {"wing": _wing_dict(wing, building_name=building.name, building_code=building.code)}


async def list_wings(
    db: AsyncSession,
    query: WingListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = (
        "name",
        "code",
        "sequence",
        "created_at",
        "total_floors",
        "total_flats",
        "is_active",
        "status",
    )
    builder = (
        ListQueryBuilder(Wing)
        .filter_eq("society_id", society_id)
        .filter_eq("building_id", query.building_id)
        .search(query.search, "name", "code", "display_name", "short_code")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="sequence")
    )
    items, total = await builder.paginate(
        db,
        page=query.page,
        page_size=query.page_size,
        serialize=lambda w: w,
    )
    building_map = await _load_buildings_map(db, {w.building_id for w in items})
    serialized = [
        _wing_dict(
            wing,
            building_name=building_map.get(wing.building_id).name
            if building_map.get(wing.building_id)
            else None,
            building_code=building_map.get(wing.building_id).code
            if building_map.get(wing.building_id)
            else None,
        )
        for wing in items
    ]
    return {
        "wings": serialized,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_wing(
    db: AsyncSession,
    wing_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    wing = await _get_or_404(db, wing_id, society_id)
    building = await _get_building_in_society(db, wing.building_id, society_id)
    return {
        "wing": _wing_dict(wing, building_name=building.name, building_code=building.code)
    }


async def update_wing(
    db: AsyncSession,
    wing_id: UUID,
    body: WingUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    wing = await _get_or_404(db, wing_id, society_id)
    building = await _get_building_in_society(db, wing.building_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "displayName": "display_name",
        "shortCode": "short_code",
        "description": "description",
        "wingType": "wing_type",
        "status": "status",
        "metadata": "metadata_json",
        "sequence": "sequence",
        "color": "color",
        "totalFloors": "total_floors",
        "totalFlats": "total_flats",
        "elevatorCount": "elevator_count",
        "emergencyStairCount": "emergency_stair_count",
        "capacity": "capacity",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(wing, orm_key, data[api_key])

    apply_update_audit(wing, actor_id)
    await db.commit()
    await db.refresh(wing)
    return {
        "wing": _wing_dict(wing, building_name=building.name, building_code=building.code)
    }


async def set_wing_active(
    db: AsyncSession,
    wing_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    wing = await _get_or_404(db, wing_id, society_id)
    building = await _get_building_in_society(db, wing.building_id, society_id)
    if active:
        soft_activate(wing, actor_id)
    else:
        soft_deactivate(wing, actor_id)
    await db.commit()
    await db.refresh(wing)
    message = "Wing activated" if active else "Wing deactivated"
    return {
        "wing": _wing_dict(wing, building_name=building.name, building_code=building.code),
        "message": message,
    }


async def _get_or_404(db: AsyncSession, wing_id: UUID, society_id: UUID) -> Wing:
    result = await db.execute(
        select(Wing).where(Wing.id == wing_id, Wing.society_id == society_id)
    )
    wing = result.scalar_one_or_none()
    if not wing:
        raise ApiError(404, "Wing not found")
    return wing
