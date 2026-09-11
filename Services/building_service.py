"""Building business logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Schemas.building import BuildingCreate, BuildingOut, BuildingUpdate
from Schemas.common import ListQueryParams, build_pagination_meta
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate
from Utils.validation_helpers import normalize_code, require_non_blank


def _building_dict(building: Building) -> Dict[str, Any]:
    return BuildingOut.from_orm_building(building).model_dump(mode="json")


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def create_building(
    db: AsyncSession,
    body: BuildingCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    from Services.platform_license_service import enforce_limit

    await enforce_limit(db, society_id, "max_buildings")
    code = normalize_code(body.code)

    existing = await db.execute(
        select(Building).where(Building.society_id == society_id, Building.code == code)
    )
    if existing.scalar_one_or_none():
        raise ApiError(409, "Building code already exists in this society")

    building = Building(
        society_id=society_id,
        name=require_non_blank(body.name, "name"),
        display_name=body.displayName or body.name,
        code=code,
        description=body.description,
        building_type=body.buildingType,
        status=body.status,
        metadata_json=body.metadata,
        address_line1=body.addressLine1,
        address_line2=body.addressLine2,
        emergency_contact_name=body.emergencyContactName,
        emergency_contact_phone=body.emergencyContactPhone,
        total_floors=body.totalFloors,
        total_units=body.totalUnits,
        planned_units=body.plannedUnits,
        occupied_units=body.occupiedUnits,
        vacant_units=body.vacantUnits,
        built_year=body.builtYear,
        has_lift=body.hasLift,
        has_parking=body.hasParking,
        image_url=body.imageUrl,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(building, actor_id)
    db.add(building)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Building code already exists in this society") from exc
    await db.refresh(building)
    return {"building": _building_dict(building)}


async def list_buildings(
    db: AsyncSession,
    query: ListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = ("name", "code", "created_at", "total_floors", "is_active", "status")
    builder = (
        ListQueryBuilder(Building)
        .filter_eq("society_id", society_id)
        .search(query.search, "name", "code", "display_name")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="name")
    )
    items, total = await builder.paginate(
        db,
        page=query.page,
        page_size=query.page_size,
        serialize=_building_dict,
    )
    return {
        "buildings": items,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_building(
    db: AsyncSession,
    building_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    building = await _get_or_404(db, building_id, society_id)
    return {"building": _building_dict(building)}


async def update_building(
    db: AsyncSession,
    building_id: UUID,
    body: BuildingUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    building = await _get_or_404(db, building_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "displayName": "display_name",
        "description": "description",
        "buildingType": "building_type",
        "status": "status",
        "metadata": "metadata_json",
        "addressLine1": "address_line1",
        "addressLine2": "address_line2",
        "emergencyContactName": "emergency_contact_name",
        "emergencyContactPhone": "emergency_contact_phone",
        "totalFloors": "total_floors",
        "totalUnits": "total_units",
        "plannedUnits": "planned_units",
        "occupiedUnits": "occupied_units",
        "vacantUnits": "vacant_units",
        "builtYear": "built_year",
        "hasLift": "has_lift",
        "hasParking": "has_parking",
        "imageUrl": "image_url",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(building, orm_key, data[api_key])

    apply_update_audit(building, actor_id)
    await db.commit()
    await db.refresh(building)
    return {"building": _building_dict(building)}


async def set_building_active(
    db: AsyncSession,
    building_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    building = await _get_or_404(db, building_id, society_id)
    if active:
        soft_activate(building, actor_id)
    else:
        soft_deactivate(building, actor_id)
    await db.commit()
    await db.refresh(building)
    message = "Building activated" if active else "Building deactivated"
    return {"building": _building_dict(building), "message": message}


async def _get_or_404(db: AsyncSession, building_id: UUID, society_id: UUID) -> Building:
    result = await db.execute(
        select(Building).where(Building.id == building_id, Building.society_id == society_id)
    )
    building = result.scalar_one_or_none()
    if not building:
        raise ApiError(404, "Building not found")
    return building
