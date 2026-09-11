"""Visit lifecycle business logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.building import Building
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.visit import Visit
from Models.visitor import Visitor
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.visit import (
    VisitCheckIn,
    VisitCheckOut,
    VisitCreate,
    VisitDecision,
    VisitListQueryParams,
    VisitOut,
    VisitUpdate,
)
from Services.visit_helpers import (
    TERMINAL_VISIT_STATUSES,
    assert_check_out_not_before_check_in,
    get_flat_in_society,
    get_occupancy_in_society,
    get_visit_in_society,
    get_visitor_in_society,
    utcnow,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def _load_context_maps(
    db: AsyncSession, visits: list[Visit]
) -> tuple[dict, dict, dict, dict, dict]:
    visitor_ids = {v.visitor_id for v in visits}
    flat_ids = {v.flat_id for v in visits}
    wing_ids = {v.wing_id for v in visits}
    building_ids = {v.building_id for v in visits}
    occupancy_ids = {v.occupancy_id for v in visits}

    visitors = {}
    if visitor_ids:
        r = await db.execute(select(Visitor).where(Visitor.id.in_(visitor_ids)))
        visitors = {x.id: x for x in r.scalars().all()}
    flats = {}
    if flat_ids:
        r = await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
        flats = {x.id: x for x in r.scalars().all()}
    wings = {}
    if wing_ids:
        r = await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))
        wings = {x.id: x for x in r.scalars().all()}
    buildings = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {x.id: x for x in r.scalars().all()}
    occupancies = {}
    if occupancy_ids:
        r = await db.execute(select(Occupancy).where(Occupancy.id.in_(occupancy_ids)))
        occupancies = {x.id: x for x in r.scalars().all()}
    return visitors, flats, wings, buildings, occupancies


async def _resident_names_for_occupancies(db: AsyncSession, occupancies: dict) -> dict:
    resident_ids = {o.resident_id for o in occupancies.values()}
    if not resident_ids:
        return {}
    r = await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
    rows = {res.id: res.name for res in r.scalars().all()}
    return {occ_id: rows.get(occ.resident_id) for occ_id, occ in occupancies.items()}


def _visit_dict(
    visit: Visit,
    *,
    visitor: Visitor | None = None,
    flat: Flat | None = None,
    wing: Wing | None = None,
    building: Building | None = None,
    resident_name: str | None = None,
) -> Dict[str, Any]:
    return VisitOut.from_orm_visit(
        visit,
        visitor_name=visitor.name if visitor else None,
        visitor_phone=visitor.phone if visitor else None,
        flat_no=flat.flat_no if flat else None,
        wing_code=wing.code if wing else None,
        building_code=building.code if building else None,
        resident_name=resident_name,
    ).model_dump(mode="json")


async def create_visit(
    db: AsyncSession,
    body: VisitCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visitor = await get_visitor_in_society(db, body.visitorId, society_id)
    occupancy = await get_occupancy_in_society(db, body.occupancyId, society_id)
    if occupancy.status != "active":
        raise ApiError(422, "Occupancy must be active")

    status = body.status
    if status == "waiting" and body.isPreapproved:
        status = "approved"

    visit = Visit(
        society_id=society_id,
        building_id=occupancy.building_id,
        wing_id=occupancy.wing_id,
        flat_id=occupancy.flat_id,
        occupancy_id=occupancy.id,
        visitor_id=visitor.id,
        purpose=body.purpose,
        visitor_type=body.visitorType,
        pass_type=body.passType,
        status=status,
        scheduled_at=body.scheduledAt,
        expected_at=body.expectedAt,
        vehicle_number=body.vehicleNumber,
        number_of_people=body.numberOfPeople,
        is_preapproved=body.isPreapproved,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=status not in TERMINAL_VISIT_STATUSES,
        version=1,
    )
    if status == "approved":
        visit.approved_by = actor_id

    apply_create_audit(visit, actor_id)
    db.add(visit)
    await db.commit()
    await db.refresh(visit)

    publish_simple(
        "VisitExpected",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={
            "visitor_name": visitor.name,
            "purpose": visit.purpose or "visit",
            "isPreapproved": visit.is_preapproved,
            "residentId": str(occupancy.resident_id),
        },
    )

    visitors, flats, wings, buildings, occupancies = await _load_context_maps(db, [visit])
    resident_names = await _resident_names_for_occupancies(db, occupancies)
    return {
        "visit": _visit_dict(
            visit,
            visitor=visitors.get(visit.visitor_id),
            flat=flats.get(visit.flat_id),
            wing=wings.get(visit.wing_id),
            building=buildings.get(visit.building_id),
            resident_name=resident_names.get(visit.occupancy_id),
        )
    }


async def list_visits(
    db: AsyncSession,
    query: VisitListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(Visit).where(Visit.society_id == society_id)
    if query.building_id:
        base = base.where(Visit.building_id == query.building_id)
    if query.wing_id:
        base = base.where(Visit.wing_id == query.wing_id)
    if query.flat_id:
        base = base.where(Visit.flat_id == query.flat_id)
    if query.occupancy_id:
        base = base.where(Visit.occupancy_id == query.occupancy_id)
    if query.visitor_id:
        base = base.where(Visit.visitor_id == query.visitor_id)
    if query.status:
        base = base.where(Visit.status == query.status)
    if query.visitor_type:
        base = base.where(Visit.visitor_type == query.visitor_type)
    if query.pass_type:
        base = base.where(Visit.pass_type == query.pass_type)
    if query.is_preapproved is not None:
        base = base.where(Visit.is_preapproved == query.is_preapproved)
    if query.is_active is not None:
        base = base.where(Visit.is_active == query.is_active)
    if query.from_date:
        base = base.where(Visit.created_at >= query.from_date)
    if query.to_date:
        base = base.where(Visit.created_at <= query.to_date)

    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        visitor_ids_subq = select(Visitor.id).where(
            Visitor.society_id == society_id,
            or_(
                Visitor.name.ilike(term),
                Visitor.phone.ilike(term),
                Visitor.government_id_number.ilike(term),
            ),
        )
        base = base.where(
            or_(
                Visit.visitor_id.in_(visitor_ids_subq),
                Visit.vehicle_number.ilike(term),
                Visit.purpose.ilike(term),
            )
        )

    allowed_sort = ("expected_at", "status", "visitor_type", "created_at", "check_in_time")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Visit, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    visits = list(rows)
    visitors, flats, wings, buildings, occupancies = await _load_context_maps(db, visits)
    resident_names = await _resident_names_for_occupancies(db, occupancies)
    return {
        "visits": [
            _visit_dict(
                v,
                visitor=visitors.get(v.visitor_id),
                flat=flats.get(v.flat_id),
                wing=wings.get(v.wing_id),
                building=buildings.get(v.building_id),
                resident_name=resident_names.get(v.occupancy_id),
            )
            for v in visits
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_visit(
    db: AsyncSession,
    visit_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    visitors, flats, wings, buildings, occupancies = await _load_context_maps(db, [visit])
    resident_names = await _resident_names_for_occupancies(db, occupancies)
    return {
        "visit": _visit_dict(
            visit,
            visitor=visitors.get(visit.visitor_id),
            flat=flats.get(visit.flat_id),
            wing=wings.get(visit.wing_id),
            building=buildings.get(visit.building_id),
            resident_name=resident_names.get(visit.occupancy_id),
        )
    }


async def update_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status in TERMINAL_VISIT_STATUSES:
        raise ApiError(422, f"Visit is {visit.status} and cannot be updated")

    data = body.model_dump(exclude_unset=True)
    field_map = {
        "purpose": "purpose",
        "passType": "pass_type",
        "visitorType": "visitor_type",
        "expectedAt": "expected_at",
        "vehicleNumber": "vehicle_number",
        "numberOfPeople": "number_of_people",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(visit, orm_key, data[api_key])
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return await get_visit(db, visit.id, actor_society_id=society_id)


async def approve_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitDecision,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status not in {"scheduled", "waiting"}:
        raise ApiError(422, "Only scheduled or waiting visits can be approved")
    visit.status = "approved"
    visit.approved_by = actor_id
    visit.is_active = True
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return {"visit": (await get_visit(db, visit.id, actor_society_id=society_id))["visit"]}


async def reject_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitDecision,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status not in {"scheduled", "waiting", "approved"}:
        raise ApiError(422, "Visit cannot be rejected in current status")
    visit.status = "rejected"
    visit.is_active = False
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return {"visit": (await get_visit(db, visit.id, actor_society_id=society_id))["visit"]}


async def check_in_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitCheckIn,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status in {"checked_in", "checked_out"}:
        raise ApiError(409, "Visit already checked in/out")
    if visit.status in {"cancelled", "rejected", "expired"}:
        raise ApiError(422, f"{visit.status} visits cannot be checked in")
    if visit.status not in {"approved", "waiting", "scheduled"}:
        raise ApiError(422, "Visit is not eligible for check-in")

    if visit.status in {"waiting", "scheduled"} and not visit.is_preapproved:
        raise ApiError(422, "Walk-in/scheduled visit requires approval before check-in")

    visit.status = "checked_in"
    visit.check_in_time = body.checkInTime or utcnow()
    visit.gate_in_by = actor_id
    visit.is_active = True
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return {"visit": (await get_visit(db, visit.id, actor_society_id=society_id))["visit"]}


async def check_out_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitCheckOut,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status == "checked_out":
        raise ApiError(409, "Visit already checked out")
    if visit.status != "checked_in":
        raise ApiError(422, "Visit must be checked in before check-out")

    checkout_time = body.checkOutTime or utcnow()
    assert_check_out_not_before_check_in(visit.check_in_time, checkout_time)
    visit.status = "checked_out"
    visit.check_out_time = checkout_time
    visit.gate_out_by = actor_id
    visit.is_active = False
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return {"visit": (await get_visit(db, visit.id, actor_society_id=society_id))["visit"]}


async def cancel_visit(
    db: AsyncSession,
    visit_id: UUID,
    body: VisitDecision,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await get_visit_in_society(db, visit_id, society_id)
    if visit.status in {"checked_out", "cancelled"}:
        raise ApiError(422, "Visit cannot be cancelled in current status")
    visit.status = "cancelled"
    visit.is_active = False
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    return {"visit": (await get_visit(db, visit.id, actor_society_id=society_id))["visit"]}


async def list_flat_visits(
    db: AsyncSession,
    flat_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    await get_flat_in_society(db, flat_id, society_id)
    query = VisitListQueryParams(
        page=1,
        page_size=100,
        flat_id=flat_id,
        sort_by="created_at",
        sort_order="desc",
    )
    return await list_visits(db, query, actor_society_id=society_id)


async def list_occupancy_visits(
    db: AsyncSession,
    occupancy_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    await get_occupancy_in_society(db, occupancy_id, society_id)
    query = VisitListQueryParams(
        page=1,
        page_size=100,
        occupancy_id=occupancy_id,
        sort_by="created_at",
        sort_order="desc",
    )
    return await list_visits(db, query, actor_society_id=society_id)


async def visitor_history(
    db: AsyncSession,
    visitor_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    query = VisitListQueryParams(
        page=1,
        page_size=100,
        visitor_id=visitor_id,
        sort_by="created_at",
        sort_order="desc",
    )
    data = await list_visits(db, query, actor_society_id=society_id)
    return {"history": data["visits"], "pagination": data["pagination"]}
