"""Parking business logic — zones, slots, allocations, vehicles, guard/finance/resident (Phase 14)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import cast, Date, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.parking import (
    ParkingAllocation,
    ParkingSlot,
    ParkingZone,
    ResidentVehicle,
    VisitorParkingLog,
)
from Models.resident import Resident
from Schemas.common import build_pagination_meta
from Schemas.parking import (
    AllocationListQueryParams,
    ParkingAllocateRequest,
    ParkingRevokeRequest,
    ParkingSlotCreate,
    ParkingSlotListQueryParams,
    ParkingSlotUpdate,
    ParkingTransferRequest,
    ParkingZoneCreate,
    ParkingZoneListQueryParams,
    ParkingZoneUpdate,
    VehicleCreate,
    VehicleListQueryParams,
    VehicleUpdate,
    VisitorParkingCreate,
)
from Services.parking_helpers import (
    ACTIVE_ALLOCATION_STATUS,
    allocation_to_dict,
    ensure_slot_allocatable,
    ensure_visitor_parking_allowed,
    get_allocation_in_society,
    get_slot_in_society,
    get_vehicle_in_society,
    get_visitor_log_in_society,
    get_zone_in_society,
    next_allocation_number,
    refresh_zone_slot_counts,
    require_society_id,
    slot_to_dict,
    unique_parking_code,
    vehicle_to_dict,
    visitor_log_to_dict,
    zone_to_dict,
    stamp_slot_entry,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

ZONE_FIELD_MAP = {
    "name": "name",
    "description": "description",
    "zoneType": "zone_type",
    "floorLabel": "floor_label",
    "buildingId": "building_id",
    "isVisitorAllowed": "is_visitor_allowed",
    "monthlyFeeMinor": "monthly_fee_minor",
    "visitorFeeMinor": "visitor_fee_minor",
    "additionalVehicleFeeMinor": "additional_vehicle_fee_minor",
    "notes": "notes",
    "metadata": "metadata_json",
    "isActive": "is_active",
}

SLOT_FIELD_MAP = {
    "label": "label",
    "slotCategory": "slot_category",
    "vehicleTypesAllowed": "vehicle_types_allowed",
    "status": "status",
    "floorNo": "floor_no",
    "isCovered": "is_covered",
    "isEvCharging": "is_ev_charging",
    "monthlyFeeMinor": "monthly_fee_minor",
    "notes": "notes",
    "metadata": "metadata_json",
    "isActive": "is_active",
}

VEHICLE_FIELD_MAP = {
    "make": "make",
    "model": "model",
    "color": "color",
    "isPrimary": "is_primary",
    "status": "status",
    "notes": "notes",
    "metadata": "metadata_json",
}


async def _resolve_resident(db: AsyncSession, *, actor_id: UUID, society_id: UUID) -> Resident:
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")
    return resident


async def _get_resident(db: AsyncSession, resident_id: UUID, society_id: UUID) -> Resident:
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.id == resident_id, Resident.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")
    return resident


def _apply_fields(entity: Any, data: Dict[str, Any], field_map: Dict[str, str]) -> None:
    for key, attr in field_map.items():
        if key in data and data[key] is not None:
            setattr(entity, attr, data[key])


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


async def create_zone(
    db: AsyncSession, body: ParkingZoneCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    existing = (
        await db.execute(
            select(ParkingZone.id).where(
                ParkingZone.society_id == society_id, ParkingZone.code == body.code
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ApiError(409, "Parking zone code already exists")

    zone = ParkingZone(
        society_id=society_id,
        code=body.code,
        name=body.name,
        description=body.description,
        zone_type=body.zoneType,
        floor_label=body.floorLabel,
        building_id=body.buildingId,
        total_slots=0,
        available_slots=0,
        is_visitor_allowed=body.isVisitorAllowed,
        monthly_fee_minor=body.monthlyFeeMinor,
        visitor_fee_minor=body.visitorFeeMinor,
        additional_vehicle_fee_minor=body.additionalVehicleFeeMinor,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(zone, actor_id)
    db.add(zone)
    await db.commit()
    await db.refresh(zone)

    publish_simple(
        "ParkingZoneCreated",
        society_id=society_id,
        entity_type="parking_zone",
        entity_id=zone.id,
        actor_id=actor_id,
        payload={"zoneId": str(zone.id), "code": zone.code},
    )
    return {"zone": zone_to_dict(zone)}


async def list_zones(
    db: AsyncSession, query: ParkingZoneListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ParkingZone).where(ParkingZone.society_id == society_id)
    if query.zone_type:
        base = base.where(ParkingZone.zone_type == query.zone_type)
    if query.building_id:
        base = base.where(ParkingZone.building_id == query.building_id)
    if query.is_active is not None:
        base = base.where(ParkingZone.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(ParkingZone.name.ilike(term), ParkingZone.code.ilike(term))
        )

    allowed_sort = ("created_at", "updated_at", "name", "code", "zone_type")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(ParkingZone, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    return {
        "zones": [zone_to_dict(z) for z in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def update_zone(
    db: AsyncSession,
    zone_id: UUID,
    body: ParkingZoneUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    zone = await get_zone_in_society(db, zone_id, society_id)
    _apply_fields(zone, body.model_dump(exclude_unset=True), ZONE_FIELD_MAP)
    apply_update_audit(zone, actor_id)
    await db.commit()
    await db.refresh(zone)
    return {"zone": zone_to_dict(zone)}


async def delete_zone(
    db: AsyncSession, zone_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    zone = await get_zone_in_society(db, zone_id, society_id)
    active_alloc = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ParkingAllocation)
                .join(ParkingSlot, ParkingSlot.id == ParkingAllocation.slot_id)
                .where(
                    ParkingSlot.zone_id == zone.id,
                    ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
                )
            )
        ).scalar_one()
    )
    if active_alloc:
        raise ApiError(422, "Cannot delete zone with active allocations")

    zone.is_active = False
    apply_update_audit(zone, actor_id)
    await db.commit()
    return {"zone": zone_to_dict(zone)}


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


async def create_slot(
    db: AsyncSession, body: ParkingSlotCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    zone = await get_zone_in_society(db, body.zoneId, society_id)
    existing = (
        await db.execute(
            select(ParkingSlot.id).where(
                ParkingSlot.society_id == society_id, ParkingSlot.slot_code == body.slotCode
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ApiError(409, "Parking slot code already exists")

    slot = ParkingSlot(
        society_id=society_id,
        zone_id=zone.id,
        slot_code=body.slotCode,
        label=body.label,
        slot_category=body.slotCategory,
        vehicle_types_allowed=body.vehicleTypesAllowed,
        status="available",
        floor_no=body.floorNo,
        is_covered=body.isCovered,
        is_ev_charging=body.isEvCharging,
        monthly_fee_minor=body.monthlyFeeMinor,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(slot, actor_id)
    db.add(slot)
    await db.flush()
    await refresh_zone_slot_counts(db, zone)
    await db.commit()
    await db.refresh(slot)

    publish_simple(
        "ParkingSlotCreated",
        society_id=society_id,
        entity_type="parking_slot",
        entity_id=slot.id,
        actor_id=actor_id,
        payload={"slotId": str(slot.id), "slotCode": slot.slot_code, "zoneId": str(zone.id)},
    )
    return {"slot": slot_to_dict(slot, zone=zone)}


async def list_slots(
    db: AsyncSession, query: ParkingSlotListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ParkingSlot).where(ParkingSlot.society_id == society_id)
    if query.zone_id:
        base = base.where(ParkingSlot.zone_id == query.zone_id)
    if query.status:
        base = base.where(ParkingSlot.status == query.status)
    if query.slot_category:
        base = base.where(ParkingSlot.slot_category == query.slot_category)
    if query.is_active is not None:
        base = base.where(ParkingSlot.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(ParkingSlot.slot_code.ilike(term), ParkingSlot.label.ilike(term))
        )

    allowed_sort = ("created_at", "updated_at", "slot_code", "status", "slot_category")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(ParkingSlot, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()

    zone_ids = {r.zone_id for r in rows}
    zones = {}
    if zone_ids:
        zone_rows = (
            await db.execute(select(ParkingZone).where(ParkingZone.id.in_(zone_ids)))
        ).scalars().all()
        zones = {z.id: z for z in zone_rows}

    return {
        "slots": [slot_to_dict(s, zone=zones.get(s.zone_id)) for s in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def update_slot(
    db: AsyncSession,
    slot_id: UUID,
    body: ParkingSlotUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    slot = await get_slot_in_society(db, slot_id, society_id)
    _apply_fields(slot, body.model_dump(exclude_unset=True), SLOT_FIELD_MAP)
    apply_update_audit(slot, actor_id)
    zone = await get_zone_in_society(db, slot.zone_id, society_id)
    await refresh_zone_slot_counts(db, zone)
    await db.commit()
    await db.refresh(slot)
    return {"slot": slot_to_dict(slot, zone=zone)}


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------


async def allocate_slot(
    db: AsyncSession,
    body: ParkingAllocateRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    slot = await get_slot_in_society(db, body.slotId, society_id)
    resident = await _get_resident(db, body.residentId, society_id)
    vehicle = None
    if body.vehicleId:
        vehicle = await get_vehicle_in_society(db, body.vehicleId, society_id)
        if vehicle.resident_id != resident.id:
            raise ApiError(422, "Vehicle does not belong to the resident")
        if vehicle.status != "active":
            raise ApiError(422, "Vehicle is not active")

    await ensure_slot_allocatable(db, slot, vehicle=vehicle)

    zone = await get_zone_in_society(db, slot.zone_id, society_id)
    fee = body.monthlyFeeMinor
    if fee is None:
        fee = slot.monthly_fee_minor if slot.monthly_fee_minor is not None else zone.monthly_fee_minor
    payment_status = "pending" if fee and fee > 0 else "not_required"

    allocation = ParkingAllocation(
        society_id=society_id,
        slot_id=slot.id,
        resident_id=resident.id,
        vehicle_id=vehicle.id if vehicle else None,
        allocation_number=await next_allocation_number(db, society_id),
        allocation_type=body.allocationType,
        status=ACTIVE_ALLOCATION_STATUS,
        start_date=body.startDate,
        end_date=body.endDate,
        monthly_fee_minor=fee or 0,
        payment_status=payment_status,
        allocated_by=actor_id,
        allocated_at=utcnow(),
        metadata_json={},
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(allocation, actor_id)
    db.add(allocation)
    await db.flush()

    slot.status = "reserved" if body.allocationType == "reserved" else "allocated"
    slot.current_allocation_id = allocation.id
    apply_update_audit(slot, actor_id)
    await refresh_zone_slot_counts(db, zone)
    await db.commit()
    await db.refresh(allocation)

    publish_simple(
        "ParkingAllocated",
        society_id=society_id,
        entity_type="parking_allocation",
        entity_id=allocation.id,
        actor_id=actor_id,
        payload={
            "allocationId": str(allocation.id),
            "slotId": str(slot.id),
            "residentId": str(resident.id),
        },
    )
    if fee and fee > 0:
        publish_simple(
            "ParkingChargeGenerated",
            society_id=society_id,
            entity_type="parking_allocation",
            entity_id=allocation.id,
            actor_id=actor_id,
            payload={"allocationId": str(allocation.id), "amount": fee},
        )
    return {"allocation": allocation_to_dict(allocation, slot=slot, vehicle=vehicle)}


async def transfer_allocation(
    db: AsyncSession,
    body: ParkingTransferRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    old = await get_allocation_in_society(db, body.allocationId, society_id)
    if old.status != ACTIVE_ALLOCATION_STATUS:
        raise ApiError(422, "Only active allocations can be transferred")

    old_slot = await get_slot_in_society(db, old.slot_id, society_id)
    new_slot = await get_slot_in_society(db, body.newSlotId, society_id)
    if old_slot.id == new_slot.id:
        raise ApiError(422, "New slot must be different from current slot")

    vehicle = None
    vehicle_id = body.vehicleId or old.vehicle_id
    if vehicle_id:
        vehicle = await get_vehicle_in_society(db, vehicle_id, society_id)
        if vehicle.resident_id != old.resident_id:
            raise ApiError(422, "Vehicle does not belong to the allocated resident")

    await ensure_slot_allocatable(db, new_slot, vehicle=vehicle)

    now = utcnow()
    old.status = "transferred"
    old.revoked_at = now
    old.revoke_reason = "Transferred to another slot"
    apply_update_audit(old, actor_id)

    old_slot.status = "available"
    old_slot.current_allocation_id = None
    apply_update_audit(old_slot, actor_id)

    zone_new = await get_zone_in_society(db, new_slot.zone_id, society_id)
    fee = new_slot.monthly_fee_minor
    if fee is None:
        fee = zone_new.monthly_fee_minor
    payment_status = "pending" if fee and fee > 0 else "not_required"

    new_alloc = ParkingAllocation(
        society_id=society_id,
        slot_id=new_slot.id,
        resident_id=old.resident_id,
        vehicle_id=vehicle.id if vehicle else None,
        allocation_number=await next_allocation_number(db, society_id),
        allocation_type=old.allocation_type,
        status=ACTIVE_ALLOCATION_STATUS,
        start_date=body.startDate or date.today(),
        end_date=body.endDate if body.endDate is not None else old.end_date,
        monthly_fee_minor=fee or 0,
        payment_status=payment_status,
        allocated_by=actor_id,
        allocated_at=now,
        transferred_from_allocation_id=old.id,
        metadata_json={},
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(new_alloc, actor_id)
    db.add(new_alloc)
    await db.flush()

    new_slot.status = "allocated"
    new_slot.current_allocation_id = new_alloc.id
    apply_update_audit(new_slot, actor_id)

    zone_old = await get_zone_in_society(db, old_slot.zone_id, society_id)
    await refresh_zone_slot_counts(db, zone_old)
    await refresh_zone_slot_counts(db, zone_new)
    await db.commit()
    await db.refresh(new_alloc)

    publish_simple(
        "ParkingTransferred",
        society_id=society_id,
        entity_type="parking_allocation",
        entity_id=new_alloc.id,
        actor_id=actor_id,
        payload={
            "fromAllocationId": str(old.id),
            "toAllocationId": str(new_alloc.id),
            "newSlotId": str(new_slot.id),
        },
    )
    return {
        "allocation": allocation_to_dict(new_alloc, slot=new_slot, vehicle=vehicle),
        "previousAllocationId": str(old.id),
    }


async def revoke_allocation(
    db: AsyncSession,
    body: ParkingRevokeRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    allocation = await get_allocation_in_society(db, body.allocationId, society_id)
    if allocation.status != ACTIVE_ALLOCATION_STATUS:
        raise ApiError(422, "Only active allocations can be revoked")

    slot = await get_slot_in_society(db, allocation.slot_id, society_id)
    allocation.status = "revoked"
    allocation.revoked_at = utcnow()
    allocation.revoke_reason = body.reason
    apply_update_audit(allocation, actor_id)

    slot.status = "available"
    slot.current_allocation_id = None
    apply_update_audit(slot, actor_id)

    zone = await get_zone_in_society(db, slot.zone_id, society_id)
    await refresh_zone_slot_counts(db, zone)
    await db.commit()

    publish_simple(
        "ParkingRevoked",
        society_id=society_id,
        entity_type="parking_allocation",
        entity_id=allocation.id,
        actor_id=actor_id,
        payload={"allocationId": str(allocation.id), "reason": body.reason},
    )
    return {"allocation": allocation_to_dict(allocation, slot=slot)}


async def list_allocations(
    db: AsyncSession, query: AllocationListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ParkingAllocation).where(ParkingAllocation.society_id == society_id)
    if query.status:
        base = base.where(ParkingAllocation.status == query.status)
    if query.resident_id:
        base = base.where(ParkingAllocation.resident_id == query.resident_id)
    if query.slot_id:
        base = base.where(ParkingAllocation.slot_id == query.slot_id)
    if query.vehicle_id:
        base = base.where(ParkingAllocation.vehicle_id == query.vehicle_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(ParkingAllocation.allocation_number.ilike(term))

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(ParkingAllocation.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()

    slot_ids = {r.slot_id for r in rows}
    vehicle_ids = {r.vehicle_id for r in rows if r.vehicle_id}
    slots = {}
    vehicles = {}
    if slot_ids:
        slots = {
            s.id: s
            for s in (
                await db.execute(select(ParkingSlot).where(ParkingSlot.id.in_(slot_ids)))
            ).scalars().all()
        }
    if vehicle_ids:
        vehicles = {
            v.id: v
            for v in (
                await db.execute(select(ResidentVehicle).where(ResidentVehicle.id.in_(vehicle_ids)))
            ).scalars().all()
        }

    return {
        "allocations": [
            allocation_to_dict(
                a, slot=slots.get(a.slot_id), vehicle=vehicles.get(a.vehicle_id) if a.vehicle_id else None
            )
            for a in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


async def create_vehicle(
    db: AsyncSession,
    body: VehicleCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    resident_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    rid = resident_id or body.residentId
    if not rid:
        raise ApiError(422, "residentId is required")
    resident = await _get_resident(db, rid, society_id)

    existing = (
        await db.execute(
            select(ResidentVehicle.id).where(
                ResidentVehicle.society_id == society_id,
                ResidentVehicle.vehicle_number == body.vehicleNumber,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ApiError(409, "Vehicle number already registered")

    if body.isPrimary:
        existing_primary = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.resident_id == resident.id,
                    ResidentVehicle.is_primary.is_(True),
                )
            )
        ).scalars().all()
        for v in existing_primary:
            v.is_primary = False

    vehicle = ResidentVehicle(
        society_id=society_id,
        resident_id=resident.id,
        user_id=resident.user_id or actor_id,
        vehicle_number=body.vehicleNumber,
        vehicle_type=body.vehicleType,
        make=body.make,
        model=body.model,
        color=body.color,
        is_primary=body.isPrimary,
        is_verified=False,
        status="active",
        parking_code=await unique_parking_code(db, society_id),
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(vehicle, actor_id)
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)

    publish_simple(
        "VehicleRegistered",
        society_id=society_id,
        entity_type="resident_vehicle",
        entity_id=vehicle.id,
        actor_id=actor_id,
        payload={"vehicleId": str(vehicle.id), "vehicleNumber": vehicle.vehicle_number},
    )
    return {"vehicle": vehicle_to_dict(vehicle)}


async def list_vehicles(
    db: AsyncSession, query: VehicleListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ResidentVehicle).where(ResidentVehicle.society_id == society_id)
    if query.resident_id:
        base = base.where(ResidentVehicle.resident_id == query.resident_id)
    if query.vehicle_type:
        base = base.where(ResidentVehicle.vehicle_type == query.vehicle_type)
    if query.status:
        base = base.where(ResidentVehicle.status == query.status)
    if query.is_active is not None:
        base = base.where(ResidentVehicle.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                ResidentVehicle.vehicle_number.ilike(term),
                ResidentVehicle.parking_code.ilike(term),
                ResidentVehicle.make.ilike(term),
                ResidentVehicle.model.ilike(term),
            )
        )

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(ResidentVehicle.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()
    return {
        "vehicles": [vehicle_to_dict(v) for v in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def update_vehicle(
    db: AsyncSession,
    vehicle_id: UUID,
    body: VehicleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    owner_resident_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    vehicle = await get_vehicle_in_society(db, vehicle_id, society_id)
    if owner_resident_id and vehicle.resident_id != owner_resident_id:
        raise ApiError(404, "Vehicle not found")

    data = body.model_dump(exclude_unset=True)
    if data.get("isPrimary") is True:
        others = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.resident_id == vehicle.resident_id,
                    ResidentVehicle.id != vehicle.id,
                    ResidentVehicle.is_primary.is_(True),
                )
            )
        ).scalars().all()
        for v in others:
            v.is_primary = False

    _apply_fields(vehicle, data, VEHICLE_FIELD_MAP)
    apply_update_audit(vehicle, actor_id)
    await db.commit()
    await db.refresh(vehicle)
    return {"vehicle": vehicle_to_dict(vehicle)}


# ---------------------------------------------------------------------------
# Visitor parking
# ---------------------------------------------------------------------------


async def create_visitor_parking(
    db: AsyncSession,
    body: VisitorParkingCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    auto_entry: bool = False,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    slot = None
    zone = None
    if body.slotId:
        slot = await get_slot_in_society(db, body.slotId, society_id)
        zone = await get_zone_in_society(db, slot.zone_id, society_id)
        ensure_visitor_parking_allowed(zone, slot)
        if slot.status not in ("available", "visitor"):
            raise ApiError(409, "Slot is not available for visitor parking")
    elif body.residentId:
        # Prefer a visitor zone if no slot specified
        zone = (
            await db.execute(
                select(ParkingZone).where(
                    ParkingZone.society_id == society_id,
                    ParkingZone.is_active.is_(True),
                    or_(
                        ParkingZone.is_visitor_allowed.is_(True),
                        ParkingZone.zone_type == "visitor",
                    ),
                ).limit(1)
            )
        ).scalar_one_or_none()

    fee = zone.visitor_fee_minor if zone else 0
    payment_status = "pending" if fee and fee > 0 else "not_required"
    now = utcnow()
    status = "active" if auto_entry else "requested"

    log = VisitorParkingLog(
        society_id=society_id,
        slot_id=slot.id if slot else None,
        visit_id=body.visitId,
        visitor_id=body.visitorId,
        resident_id=body.residentId,
        vehicle_number=body.vehicleNumber,
        vehicle_type=body.vehicleType,
        parking_code=await unique_parking_code(db, society_id),
        status=status,
        entry_at=now if auto_entry else None,
        entry_by=actor_id if auto_entry else None,
        fee_minor=fee or 0,
        payment_status=payment_status,
        purpose=body.purpose,
        metadata_json=body.metadata,
        notes=body.notes,
    )
    db.add(log)

    if auto_entry and slot:
        slot.status = "visitor"
        stamp_slot_entry(slot, at=now, actor_id=actor_id)
        apply_update_audit(slot, actor_id)
        if zone:
            await refresh_zone_slot_counts(db, zone)

    await db.commit()
    await db.refresh(log)

    publish_simple(
        "VisitorParkingCreated",
        society_id=society_id,
        entity_type="visitor_parking_log",
        entity_id=log.id,
        actor_id=actor_id,
        payload={"logId": str(log.id), "vehicleNumber": log.vehicle_number},
    )
    if fee and fee > 0:
        publish_simple(
            "ParkingChargeGenerated",
            society_id=society_id,
            entity_type="visitor_parking_log",
            entity_id=log.id,
            actor_id=actor_id,
            payload={"logId": str(log.id), "amount": fee},
        )
    return {"visitorParking": visitor_log_to_dict(log)}

# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------


async def list_parking_revenue(
    db: AsyncSession,
    *,
    actor_society_id: UUID | None,
    from_date: Optional[date],
    to_date: Optional[date],
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)

    alloc_stmt = select(
        func.coalesce(func.sum(ParkingAllocation.monthly_fee_minor), 0),
        func.count(ParkingAllocation.id),
    ).where(
        ParkingAllocation.society_id == society_id,
        ParkingAllocation.payment_status == "paid",
    )
    if from_date:
        alloc_stmt = alloc_stmt.where(ParkingAllocation.start_date >= from_date)
    if to_date:
        alloc_stmt = alloc_stmt.where(ParkingAllocation.start_date <= to_date)
    alloc_total, alloc_count = (await db.execute(alloc_stmt)).one()

    visitor_stmt = select(
        func.coalesce(func.sum(VisitorParkingLog.fee_minor), 0),
        func.count(VisitorParkingLog.id),
    ).where(
        VisitorParkingLog.society_id == society_id,
        VisitorParkingLog.payment_status == "paid",
    )
    if from_date:
        visitor_stmt = visitor_stmt.where(cast(VisitorParkingLog.entry_at, Date) >= from_date)
    if to_date:
        visitor_stmt = visitor_stmt.where(cast(VisitorParkingLog.entry_at, Date) <= to_date)
    visitor_total, visitor_count = (await db.execute(visitor_stmt)).one()

    return {
        "allocationRevenue": int(alloc_total),
        "allocationCount": int(alloc_count),
        "visitorRevenue": int(visitor_total),
        "visitorCount": int(visitor_count),
        "totalRevenue": int(alloc_total) + int(visitor_total),
    }


async def list_parking_payments(
    db: AsyncSession, query: AllocationListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ParkingAllocation).where(
        ParkingAllocation.society_id == society_id,
        ParkingAllocation.monthly_fee_minor > 0,
    )
    if query.status:
        base = base.where(ParkingAllocation.status == query.status)
    if query.resident_id:
        base = base.where(ParkingAllocation.resident_id == query.resident_id)

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(ParkingAllocation.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()
    return {
        "payments": [allocation_to_dict(a) for a in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def process_refund(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    allocation_id: Optional[UUID] = None,
    visitor_log_id: Optional[UUID] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)

    if allocation_id:
        allocation = await get_allocation_in_society(db, allocation_id, society_id)
        if allocation.payment_status != "paid":
            raise ApiError(422, "Allocation has no payment eligible for refund")
        allocation.payment_status = "refunded"
        apply_update_audit(allocation, actor_id)
        await db.commit()
        publish_simple(
            "ParkingRefundProcessed",
            society_id=society_id,
            entity_type="parking_allocation",
            entity_id=allocation.id,
            actor_id=actor_id,
            payload={"allocationId": str(allocation.id), "reason": reason},
        )
        return {
            "allocationId": str(allocation.id),
            "paymentStatus": allocation.payment_status,
        }

    log = await get_visitor_log_in_society(db, visitor_log_id, society_id)  # type: ignore[arg-type]
    if log.payment_status != "paid":
        raise ApiError(422, "Visitor parking has no payment eligible for refund")
    log.payment_status = "refunded"
    await db.commit()
    publish_simple(
        "ParkingRefundProcessed",
        society_id=society_id,
        entity_type="visitor_parking_log",
        entity_id=log.id,
        actor_id=actor_id,
        payload={"logId": str(log.id), "reason": reason},
    )
    return {"visitorLogId": str(log.id), "paymentStatus": log.payment_status}


# ---------------------------------------------------------------------------
# Resident portal
# ---------------------------------------------------------------------------


async def resident_parking_overview(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)

    allocations = (
        await db.execute(
            select(ParkingAllocation).where(
                ParkingAllocation.resident_id == resident.id,
                ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
            )
        )
    ).scalars().all()
    vehicles = (
        await db.execute(
            select(ResidentVehicle).where(
                ResidentVehicle.resident_id == resident.id,
                ResidentVehicle.is_active.is_(True),
            )
        )
    ).scalars().all()

    slot_ids = {a.slot_id for a in allocations}
    slots = {}
    if slot_ids:
        slots = {
            s.id: s
            for s in (
                await db.execute(select(ParkingSlot).where(ParkingSlot.id.in_(slot_ids)))
            ).scalars().all()
        }
    vehicle_map = {v.id: v for v in vehicles}

    return {
        "allocations": [
            allocation_to_dict(
                a,
                slot=slots.get(a.slot_id),
                vehicle=vehicle_map.get(a.vehicle_id) if a.vehicle_id else None,
            )
            for a in allocations
        ],
        "vehicles": [vehicle_to_dict(v) for v in vehicles],
    }


async def resident_list_vehicles(
    db: AsyncSession, query: VehicleListQueryParams, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    query.resident_id = resident.id
    return await list_vehicles(db, query, actor_society_id=society_id)


async def resident_create_vehicle(
    db: AsyncSession, body: VehicleCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    return await create_vehicle(
        db, body, actor_id=actor_id, actor_society_id=society_id, resident_id=resident.id
    )


async def resident_update_vehicle(
    db: AsyncSession,
    vehicle_id: UUID,
    body: VehicleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    return await update_vehicle(
        db,
        vehicle_id,
        body,
        actor_id=actor_id,
        actor_society_id=society_id,
        owner_resident_id=resident.id,
    )


async def resident_create_visitor_parking(
    db: AsyncSession, body: VisitorParkingCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    payload = body.model_copy(update={"residentId": resident.id})
    return await create_visitor_parking(
        db, payload, actor_id=actor_id, actor_society_id=society_id, auto_entry=False
    )


async def resident_parking_history(
    db: AsyncSession, query: AllocationListQueryParams, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    query.resident_id = resident.id
    return await list_allocations(db, query, actor_society_id=society_id)


async def resident_parking_receipt(
    db: AsyncSession, allocation_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    allocation = await get_allocation_in_society(db, allocation_id, society_id)
    if allocation.resident_id != resident.id:
        raise ApiError(404, "Parking allocation not found")
    slot = await get_slot_in_society(db, allocation.slot_id, society_id)
    vehicle = None
    if allocation.vehicle_id:
        vehicle = await get_vehicle_in_society(db, allocation.vehicle_id, society_id)

    return {
        "receipt": {
            "allocationId": str(allocation.id),
            "allocationNumber": allocation.allocation_number,
            "slotCode": slot.slot_code,
            "residentName": resident.name,
            "vehicleNumber": vehicle.vehicle_number if vehicle else None,
            "allocationType": allocation.allocation_type,
            "status": allocation.status,
            "startDate": allocation.start_date.isoformat(),
            "endDate": allocation.end_date.isoformat() if allocation.end_date else None,
            "monthlyFeeMinor": allocation.monthly_fee_minor,
            "paymentStatus": allocation.payment_status,
            "issuedAt": utcnow().isoformat(),
        }
    }
