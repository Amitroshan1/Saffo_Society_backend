"""Occupancy business logic — move-in, move-out, flat derivation."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.occupancy import (
    OccupancyCreate,
    OccupancyListQueryParams,
    OccupancyMoveOut,
    OccupancyOut,
    OccupancyUpdate,
)
from Services.occupancy_helpers import (
    clear_user_flat_if_no_active_occupancy,
    demote_other_primaries,
    derive_flat_from_occupancies,
    get_flat_in_society,
    get_resident_in_society,
    sync_user_flat_for_resident,
    validate_move_out_dates,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def _load_context_maps(
    db: AsyncSession, occupancies: list[Occupancy]
) -> tuple[dict, dict, dict, dict]:
    flat_ids = {o.flat_id for o in occupancies}
    resident_ids = {o.resident_id for o in occupancies}
    building_ids = {o.building_id for o in occupancies}
    wing_ids = {o.wing_id for o in occupancies}

    flats = {}
    if flat_ids:
        r = await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
        flats = {f.id: f for f in r.scalars().all()}
    residents = {}
    if resident_ids:
        r = await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
        residents = {x.id: x for x in r.scalars().all()}
    buildings = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {b.id: b for b in r.scalars().all()}
    wings = {}
    if wing_ids:
        r = await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))
        wings = {w.id: w for w in r.scalars().all()}
    return flats, residents, buildings, wings


def _occupancy_dict(
    occ: Occupancy,
    *,
    flat: Optional[Flat] = None,
    resident: Optional[Resident] = None,
    building: Optional[Building] = None,
    wing: Optional[Wing] = None,
) -> Dict[str, Any]:
    return OccupancyOut.from_orm_occupancy(
        occ,
        flat_no=flat.flat_no if flat else None,
        floor_no=flat.floor_no if flat else None,
        wing_code=wing.code if wing else None,
        wing_name=wing.name if wing else None,
        building_name=building.name if building else None,
        building_code=building.code if building else None,
        resident_name=resident.name if resident else None,
        resident_code=resident.code if resident else None,
        resident_phone=resident.phone if resident else None,
        user_id=resident.user_id if resident else None,
    ).model_dump(mode="json")


async def create_occupancy(
    db: AsyncSession,
    body: OccupancyCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    flat = await get_flat_in_society(db, body.flatId, society_id, require_active=True)
    resident = await get_resident_in_society(db, body.residentId, society_id)
    if not resident.is_active:
        raise ApiError(422, "Resident is inactive")

    dup = await db.execute(
        select(Occupancy).where(
            Occupancy.flat_id == flat.id,
            Occupancy.resident_id == resident.id,
            Occupancy.status == "active",
        )
    )
    if dup.scalar_one_or_none():
        raise ApiError(409, "Active occupancy already exists for this resident and flat")

    if body.isPrimary:
        await demote_other_primaries(db, flat.id)

    occ = Occupancy(
        society_id=society_id,
        building_id=flat.building_id,
        wing_id=flat.wing_id,
        flat_id=flat.id,
        resident_id=resident.id,
        role=body.role,
        is_primary=body.isPrimary,
        status="active",
        move_in_date=body.moveInDate,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(occ, actor_id)
    db.add(occ)
    try:
        await db.flush()
        await derive_flat_from_occupancies(db, flat)
        await sync_user_flat_for_resident(db, resident, preferred_flat_id=flat.id)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Occupancy conflict (primary or duplicate active)") from exc

    await db.refresh(occ)
    flats, residents, buildings, wings = await _load_context_maps(db, [occ])
    return {
        "occupancy": _occupancy_dict(
            occ,
            flat=flats.get(occ.flat_id),
            resident=residents.get(occ.resident_id),
            building=buildings.get(occ.building_id),
            wing=wings.get(occ.wing_id),
        )
    }


async def list_occupancies(
    db: AsyncSession,
    query: OccupancyListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    status_filter = "active" if query.current_only else query.status

    base = select(Occupancy).where(Occupancy.society_id == society_id)
    if query.building_id:
        base = base.where(Occupancy.building_id == query.building_id)
    if query.wing_id:
        base = base.where(Occupancy.wing_id == query.wing_id)
    if query.flat_id:
        base = base.where(Occupancy.flat_id == query.flat_id)
    if query.resident_id:
        base = base.where(Occupancy.resident_id == query.resident_id)
    if query.role:
        base = base.where(Occupancy.role == query.role)
    if status_filter:
        base = base.where(Occupancy.status == status_filter)
    if query.is_primary is not None:
        base = base.where(Occupancy.is_primary == query.is_primary)
    if query.is_active is not None:
        base = base.where(Occupancy.is_active == query.is_active)

    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        resident_ids_subq = select(Resident.id).where(
            Resident.society_id == society_id,
            or_(
                Resident.name.ilike(term),
                Resident.phone.ilike(term),
                Resident.code.ilike(term),
            ),
        )
        base = base.where(Occupancy.resident_id.in_(resident_ids_subq))

    allowed_sort = ("move_in_date", "role", "status", "created_at", "is_active")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "move_in_date"
    sort_col = getattr(Occupancy, sort_field)
    if query.sort_order.lower() == "asc":
        base = base.order_by(sort_col.asc())
    else:
        base = base.order_by(sort_col.desc())

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())

    offset = (query.page - 1) * query.page_size
    rows = (await db.execute(base.offset(offset).limit(query.page_size))).scalars().all()
    items = list(rows)

    flats, residents, buildings, wings = await _load_context_maps(db, items)
    serialized = [
        _occupancy_dict(
            o,
            flat=flats.get(o.flat_id),
            resident=residents.get(o.resident_id),
            building=buildings.get(o.building_id),
            wing=wings.get(o.wing_id),
        )
        for o in items
    ]
    return {
        "occupancies": serialized,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_occupancy(
    db: AsyncSession,
    occupancy_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    occ = await _get_or_404(db, occupancy_id, society_id)
    flats, residents, buildings, wings = await _load_context_maps(db, [occ])
    return {
        "occupancy": _occupancy_dict(
            occ,
            flat=flats.get(occ.flat_id),
            resident=residents.get(occ.resident_id),
            building=buildings.get(occ.building_id),
            wing=wings.get(occ.wing_id),
        )
    }


async def update_occupancy(
    db: AsyncSession,
    occupancy_id: UUID,
    body: OccupancyUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    occ = await _get_or_404(db, occupancy_id, society_id)
    if occ.status != "active":
        raise ApiError(422, "Only active occupancies can be updated")

    data = body.model_dump(exclude_unset=True)
    if data.get("role") == "domestic_help" and data.get("isPrimary"):
        raise ApiError(422, "domestic_help cannot be primary")
    if data.get("isPrimary") and occ.role == "domestic_help":
        raise ApiError(422, "domestic_help cannot be primary")

    if data.get("isPrimary"):
        await demote_other_primaries(db, occ.flat_id, except_id=occ.id)

    field_map = {
        "role": "role",
        "isPrimary": "is_primary",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(occ, orm_key, data[api_key])

    apply_update_audit(occ, actor_id)
    flat = await get_flat_in_society(db, occ.flat_id, society_id)
    resident = await get_resident_in_society(db, occ.resident_id, society_id)
    await derive_flat_from_occupancies(db, flat)
    await sync_user_flat_for_resident(db, resident, preferred_flat_id=flat.id)
    await db.commit()
    await db.refresh(occ)

    flats, residents, buildings, wings = await _load_context_maps(db, [occ])
    return {
        "occupancy": _occupancy_dict(
            occ,
            flat=flats.get(occ.flat_id),
            resident=residents.get(occ.resident_id),
            building=buildings.get(occ.building_id),
            wing=wings.get(occ.wing_id),
        )
    }


async def move_out_occupancy(
    db: AsyncSession,
    occupancy_id: UUID,
    body: OccupancyMoveOut,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    occ = await _get_or_404(db, occupancy_id, society_id)
    if occ.status != "active":
        raise ApiError(422, "Occupancy is not active")

    move_out = body.moveOutDate or date.today()
    validate_move_out_dates(occ.move_in_date, move_out)

    occ.move_out_date = move_out
    occ.ended_reason = body.endedReason
    occ.status = "ended"
    occ.is_active = False
    if body.notes:
        occ.notes = body.notes
    apply_update_audit(occ, actor_id)

    flat = await get_flat_in_society(db, occ.flat_id, society_id)
    resident = await get_resident_in_society(db, occ.resident_id, society_id)
    await derive_flat_from_occupancies(db, flat)
    if resident.user_id:
        await clear_user_flat_if_no_active_occupancy(db, resident.user_id, society_id)
        await sync_user_flat_for_resident(db, resident)
    await db.commit()
    await db.refresh(occ)

    flats, residents, buildings, wings = await _load_context_maps(db, [occ])
    return {
        "occupancy": _occupancy_dict(
            occ,
            flat=flats.get(occ.flat_id),
            resident=residents.get(occ.resident_id),
            building=buildings.get(occ.building_id),
            wing=wings.get(occ.wing_id),
        ),
        "message": "Occupancy ended",
    }


async def cancel_occupancy(
    db: AsyncSession,
    occupancy_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    occ = await _get_or_404(db, occupancy_id, society_id)
    if occ.status != "active":
        raise ApiError(422, "Only active occupancies can be cancelled")

    occ.status = "cancelled"
    occ.is_active = False
    occ.ended_reason = "other"
    apply_update_audit(occ, actor_id)

    flat = await get_flat_in_society(db, occ.flat_id, society_id)
    resident = await get_resident_in_society(db, occ.resident_id, society_id)
    await derive_flat_from_occupancies(db, flat)
    if resident.user_id:
        await clear_user_flat_if_no_active_occupancy(db, resident.user_id, society_id)
        await sync_user_flat_for_resident(db, resident)
    await db.commit()
    await db.refresh(occ)

    flats, residents, buildings, wings = await _load_context_maps(db, [occ])
    return {
        "occupancy": _occupancy_dict(
            occ,
            flat=flats.get(occ.flat_id),
            resident=residents.get(occ.resident_id),
            building=buildings.get(occ.building_id),
            wing=wings.get(occ.wing_id),
        ),
        "message": "Occupancy cancelled",
    }


async def _get_or_404(db: AsyncSession, occupancy_id: UUID, society_id: UUID) -> Occupancy:
    result = await db.execute(
        select(Occupancy).where(Occupancy.id == occupancy_id, Occupancy.society_id == society_id)
    )
    occ = result.scalar_one_or_none()
    if not occ:
        raise ApiError(404, "Occupancy not found")
    return occ


async def list_flat_occupancies(
    db: AsyncSession,
    flat_id: UUID,
    *,
    actor_society_id: UUID | None,
    current_only: bool = True,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    await get_flat_in_society(db, flat_id, society_id)
    query = OccupancyListQueryParams(
        page=1,
        page_size=100,
        flat_id=flat_id,
        current_only=current_only,
        sort_by="move_in_date",
        sort_order="desc",
    )
    return await list_occupancies(db, query, actor_society_id=society_id)


async def get_flat_household(
    db: AsyncSession,
    flat_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    data = await list_flat_occupancies(
        db, flat_id, actor_society_id=actor_society_id, current_only=True
    )
    return {"household": data["occupancies"]}
