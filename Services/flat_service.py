"""Flat business logic."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.flat import FlatCreate, FlatListQueryParams, FlatOut, FlatUpdate
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate
from Utils.validation_helpers import normalize_code, require_non_blank


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _flat_dict(
    flat: Flat,
    *,
    building_name: Optional[str] = None,
    building_code: Optional[str] = None,
    wing_name: Optional[str] = None,
    wing_code: Optional[str] = None,
) -> Dict[str, Any]:
    return FlatOut.from_orm_flat(
        flat,
        building_name=building_name,
        building_code=building_code,
        wing_name=wing_name,
        wing_code=wing_code,
    ).model_dump(mode="json")


async def _load_buildings_map(
    db: AsyncSession, building_ids: set[UUID]
) -> Dict[UUID, Building]:
    if not building_ids:
        return {}
    result = await db.execute(select(Building).where(Building.id.in_(building_ids)))
    return {b.id: b for b in result.scalars().all()}


async def _load_wings_map(db: AsyncSession, wing_ids: set[UUID]) -> Dict[UUID, Wing]:
    if not wing_ids:
        return {}
    result = await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))
    return {w.id: w for w in result.scalars().all()}


async def _get_wing_in_society(
    db: AsyncSession, wing_id: UUID, society_id: UUID
) -> Wing:
    result = await db.execute(
        select(Wing).where(Wing.id == wing_id, Wing.society_id == society_id)
    )
    wing = result.scalar_one_or_none()
    if not wing:
        raise ApiError(404, "Wing not found")
    return wing


async def create_flat(
    db: AsyncSession,
    body: FlatCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    from Services.platform_license_service import enforce_limit

    await enforce_limit(db, society_id, "max_flats")
    wing = await _get_wing_in_society(db, body.wingId, society_id)
    flat_no = normalize_code(body.flatNo)

    existing = await db.execute(
        select(Flat).where(Flat.wing_id == wing.id, Flat.flat_no == flat_no)
    )
    if existing.scalar_one_or_none():
        raise ApiError(409, "Flat number already exists in this wing")

    flat = Flat(
        society_id=society_id,
        building_id=wing.building_id,
        wing_id=wing.id,
        flat_no=flat_no,
        floor_no=require_non_blank(body.floorNo, "floorNo"),
        flat_type=body.flatType,
        usage_type=body.usageType,
        status=body.status,
        ownership_type=body.ownershipType,
        area_sqft=body.areaSqft,
        area_type=body.areaType,
        intercom=body.intercom,
        metadata_json=body.metadata,
        sequence=body.sequence,
        color=body.color,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(flat, actor_id)
    db.add(flat)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Flat number already exists in this wing") from exc
    await db.refresh(flat)

    building_map = await _load_buildings_map(db, {flat.building_id})
    building = building_map.get(flat.building_id)
    return {
        "flat": _flat_dict(
            flat,
            building_name=building.name if building else None,
            building_code=building.code if building else None,
            wing_name=wing.name,
            wing_code=wing.code,
        )
    }


async def list_flats(
    db: AsyncSession,
    query: FlatListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = (
        "flat_no",
        "floor_no",
        "sequence",
        "flat_type",
        "usage_type",
        "status",
        "created_at",
        "is_active",
    )
    builder = (
        ListQueryBuilder(Flat)
        .filter_eq("society_id", society_id)
        .filter_eq("building_id", query.building_id)
        .filter_eq("wing_id", query.wing_id)
        .filter_eq("floor_no", query.floor_no)
        .search(query.search, "flat_no", "floor_no", "intercom")
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            allowed_sort,
            default="sequence",
            secondary="flat_no",
        )
    )
    items, total = await builder.paginate(
        db,
        page=query.page,
        page_size=query.page_size,
        serialize=lambda f: f,
    )
    building_map = await _load_buildings_map(db, {f.building_id for f in items})
    wing_map = await _load_wings_map(db, {f.wing_id for f in items})
    serialized = []
    for flat in items:
        building = building_map.get(flat.building_id)
        wing = wing_map.get(flat.wing_id)
        serialized.append(
            _flat_dict(
                flat,
                building_name=building.name if building else None,
                building_code=building.code if building else None,
                wing_name=wing.name if wing else None,
                wing_code=wing.code if wing else None,
            )
        )
    return {
        "flats": serialized,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_flat(
    db: AsyncSession,
    flat_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    flat = await _get_or_404(db, flat_id, society_id)
    building_map = await _load_buildings_map(db, {flat.building_id})
    wing_map = await _load_wings_map(db, {flat.wing_id})
    building = building_map.get(flat.building_id)
    wing = wing_map.get(flat.wing_id)
    return {
        "flat": _flat_dict(
            flat,
            building_name=building.name if building else None,
            building_code=building.code if building else None,
            wing_name=wing.name if wing else None,
            wing_code=wing.code if wing else None,
        )
    }


async def update_flat(
    db: AsyncSession,
    flat_id: UUID,
    body: FlatUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    flat = await _get_or_404(db, flat_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "floorNo": "floor_no",
        "flatType": "flat_type",
        "usageType": "usage_type",
        "status": "status",
        "ownershipType": "ownership_type",
        "areaSqft": "area_sqft",
        "areaType": "area_type",
        "intercom": "intercom",
        "metadata": "metadata_json",
        "sequence": "sequence",
        "color": "color",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(flat, orm_key, data[api_key])

    apply_update_audit(flat, actor_id)
    await db.commit()
    await db.refresh(flat)

    building_map = await _load_buildings_map(db, {flat.building_id})
    wing_map = await _load_wings_map(db, {flat.wing_id})
    building = building_map.get(flat.building_id)
    wing = wing_map.get(flat.wing_id)
    return {
        "flat": _flat_dict(
            flat,
            building_name=building.name if building else None,
            building_code=building.code if building else None,
            wing_name=wing.name if wing else None,
            wing_code=wing.code if wing else None,
        )
    }


async def set_flat_active(
    db: AsyncSession,
    flat_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    flat = await _get_or_404(db, flat_id, society_id)
    if active:
        soft_activate(flat, actor_id)
    else:
        soft_deactivate(flat, actor_id)
    await db.commit()
    await db.refresh(flat)

    building_map = await _load_buildings_map(db, {flat.building_id})
    wing_map = await _load_wings_map(db, {flat.wing_id})
    building = building_map.get(flat.building_id)
    wing = wing_map.get(flat.wing_id)
    message = "Flat activated" if active else "Flat deactivated"
    return {
        "flat": _flat_dict(
            flat,
            building_name=building.name if building else None,
            building_code=building.code if building else None,
            wing_name=wing.name if wing else None,
            wing_code=wing.code if wing else None,
        ),
        "message": message,
    }


async def _get_or_404(db: AsyncSession, flat_id: UUID, society_id: UUID) -> Flat:
    result = await db.execute(
        select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id)
    )
    flat = result.scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")
    return flat
