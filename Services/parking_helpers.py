"""Parking helpers — lookups, numbering, validation, serialization."""

from __future__ import annotations

import random
import string
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.parking import (
    ParkingAllocation,
    ParkingSlot,
    ParkingZone,
    ResidentVehicle,
    VisitorParkingLog,
)
from Utils.errors import ApiError

ACTIVE_ALLOCATION_STATUS = "active"


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def get_zone_in_society(
    db: AsyncSession, zone_id: UUID, society_id: UUID
) -> ParkingZone:
    result = await db.execute(
        select(ParkingZone).where(
            ParkingZone.id == zone_id, ParkingZone.society_id == society_id
        )
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise ApiError(404, "Parking zone not found")
    return zone


async def get_slot_in_society(
    db: AsyncSession, slot_id: UUID, society_id: UUID
) -> ParkingSlot:
    result = await db.execute(
        select(ParkingSlot).where(
            ParkingSlot.id == slot_id, ParkingSlot.society_id == society_id
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise ApiError(404, "Parking slot not found")
    return slot


async def get_vehicle_in_society(
    db: AsyncSession, vehicle_id: UUID, society_id: UUID
) -> ResidentVehicle:
    result = await db.execute(
        select(ResidentVehicle).where(
            ResidentVehicle.id == vehicle_id, ResidentVehicle.society_id == society_id
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise ApiError(404, "Vehicle not found")
    return vehicle


async def get_allocation_in_society(
    db: AsyncSession, allocation_id: UUID, society_id: UUID
) -> ParkingAllocation:
    result = await db.execute(
        select(ParkingAllocation).where(
            ParkingAllocation.id == allocation_id,
            ParkingAllocation.society_id == society_id,
        )
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise ApiError(404, "Parking allocation not found")
    return allocation


async def get_visitor_log_in_society(
    db: AsyncSession, log_id: UUID, society_id: UUID
) -> VisitorParkingLog:
    result = await db.execute(
        select(VisitorParkingLog).where(
            VisitorParkingLog.id == log_id, VisitorParkingLog.society_id == society_id
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise ApiError(404, "Visitor parking log not found")
    return log


async def next_allocation_number(db: AsyncSession, society_id: UUID) -> str:
    count = (
        await db.execute(
            select(func.count()).where(ParkingAllocation.society_id == society_id)
        )
    ).scalar_one()
    return f"ALC-{int(count) + 1:06d}"


def generate_parking_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=6))


async def unique_parking_code(db: AsyncSession, society_id: UUID) -> str:
    for _ in range(10):
        code = generate_parking_code()
        exists = (
            await db.execute(
                select(ResidentVehicle.id).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.parking_code == code,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            visitor_exists = (
                await db.execute(
                    select(VisitorParkingLog.id).where(
                        VisitorParkingLog.society_id == society_id,
                        VisitorParkingLog.parking_code == code,
                        VisitorParkingLog.status.in_(("requested", "active")),
                    )
                )
            ).scalar_one_or_none()
            if not visitor_exists:
                return code
    raise ApiError(500, "Unable to generate unique parking code")


async def refresh_zone_slot_counts(db: AsyncSession, zone: ParkingZone) -> None:
    total = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.zone_id == zone.id, ParkingSlot.is_active.is_(True)
                )
            )
        ).scalar_one()
    )
    available = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.zone_id == zone.id,
                    ParkingSlot.is_active.is_(True),
                    ParkingSlot.status == "available",
                )
            )
        ).scalar_one()
    )
    zone.total_slots = total
    zone.available_slots = available


async def ensure_slot_allocatable(
    db: AsyncSession,
    slot: ParkingSlot,
    *,
    vehicle: Optional[ResidentVehicle] = None,
    exclude_allocation_id: Optional[UUID] = None,
) -> None:
    if not slot.is_active:
        raise ApiError(422, "Parking slot is inactive")
    if slot.status in ("maintenance", "blocked", "inactive"):
        raise ApiError(422, f"Parking slot is {slot.status}")

    active_stmt = select(ParkingAllocation).where(
        ParkingAllocation.slot_id == slot.id,
        ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
    )
    if exclude_allocation_id:
        active_stmt = active_stmt.where(ParkingAllocation.id != exclude_allocation_id)
    existing = (await db.execute(active_stmt)).scalar_one_or_none()
    if existing:
        raise ApiError(409, "Slot already has an active allocation")

    if vehicle:
        allowed = {
            p.strip().lower()
            for p in (slot.vehicle_types_allowed or "").split(",")
            if p.strip()
        }
        if allowed and vehicle.vehicle_type not in allowed:
            raise ApiError(
                422,
                f"Vehicle type '{vehicle.vehicle_type}' is not allowed on this slot",
            )
        if slot.slot_category == "ev" or slot.is_ev_charging:
            if vehicle.vehicle_type != "ev":
                raise ApiError(422, "EV slots require an EV vehicle")


def ensure_visitor_parking_allowed(zone: ParkingZone, slot: Optional[ParkingSlot]) -> None:
    if not zone.is_visitor_allowed and zone.zone_type != "visitor":
        raise ApiError(422, "Visitor parking is not allowed in this zone")
    if slot and slot.slot_category not in ("visitor", "standard") and slot.status not in (
        "available",
        "visitor",
    ):
        if slot.slot_category != "visitor":
            raise ApiError(422, "Selected slot is not available for visitor parking")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def zone_to_dict(zone: ParkingZone) -> Dict[str, Any]:
    return {
        "id": str(zone.id),
        "societyId": str(zone.society_id),
        "code": zone.code,
        "name": zone.name,
        "description": zone.description,
        "zoneType": zone.zone_type,
        "floorLabel": zone.floor_label,
        "buildingId": str(zone.building_id) if zone.building_id else None,
        "totalSlots": zone.total_slots,
        "availableSlots": zone.available_slots,
        "isVisitorAllowed": zone.is_visitor_allowed,
        "monthlyFeeMinor": zone.monthly_fee_minor,
        "visitorFeeMinor": zone.visitor_fee_minor,
        "additionalVehicleFeeMinor": zone.additional_vehicle_fee_minor,
        "metadata": zone.metadata_json or {},
        "notes": zone.notes,
        "isActive": zone.is_active,
        "version": zone.version,
        "createdAt": zone.created_at.isoformat() if zone.created_at else None,
        "updatedAt": zone.updated_at.isoformat() if zone.updated_at else None,
    }


def slot_to_dict(
    slot: ParkingSlot, *, zone: Optional[ParkingZone] = None
) -> Dict[str, Any]:
    return {
        "id": str(slot.id),
        "societyId": str(slot.society_id),
        "zoneId": str(slot.zone_id),
        "zoneName": zone.name if zone else None,
        "slotCode": slot.slot_code,
        "label": slot.label,
        "slotCategory": slot.slot_category,
        "vehicleTypesAllowed": slot.vehicle_types_allowed,
        "status": slot.status,
        "floorNo": slot.floor_no,
        "isCovered": slot.is_covered,
        "isEvCharging": slot.is_ev_charging,
        "monthlyFeeMinor": slot.monthly_fee_minor,
        "currentAllocationId": (
            str(slot.current_allocation_id) if slot.current_allocation_id else None
        ),
        "metadata": slot.metadata_json or {},
        "notes": slot.notes,
        "isActive": slot.is_active,
        "version": slot.version,
        "createdAt": slot.created_at.isoformat() if slot.created_at else None,
        "updatedAt": slot.updated_at.isoformat() if slot.updated_at else None,
    }


def vehicle_to_dict(vehicle: ResidentVehicle) -> Dict[str, Any]:
    return {
        "id": str(vehicle.id),
        "societyId": str(vehicle.society_id),
        "residentId": str(vehicle.resident_id),
        "userId": str(vehicle.user_id) if vehicle.user_id else None,
        "vehicleNumber": vehicle.vehicle_number,
        "vehicleType": vehicle.vehicle_type,
        "make": vehicle.make,
        "model": vehicle.model,
        "color": vehicle.color,
        "isPrimary": vehicle.is_primary,
        "isVerified": vehicle.is_verified,
        "status": vehicle.status,
        "parkingCode": vehicle.parking_code,
        "metadata": vehicle.metadata_json or {},
        "notes": vehicle.notes,
        "isActive": vehicle.is_active,
        "version": vehicle.version,
        "createdAt": vehicle.created_at.isoformat() if vehicle.created_at else None,
        "updatedAt": vehicle.updated_at.isoformat() if vehicle.updated_at else None,
    }


def allocation_to_dict(
    allocation: ParkingAllocation,
    *,
    slot: Optional[ParkingSlot] = None,
    vehicle: Optional[ResidentVehicle] = None,
) -> Dict[str, Any]:
    return {
        "id": str(allocation.id),
        "societyId": str(allocation.society_id),
        "slotId": str(allocation.slot_id),
        "slotCode": slot.slot_code if slot else None,
        "residentId": str(allocation.resident_id),
        "vehicleId": str(allocation.vehicle_id) if allocation.vehicle_id else None,
        "vehicleNumber": vehicle.vehicle_number if vehicle else None,
        "allocationNumber": allocation.allocation_number,
        "allocationType": allocation.allocation_type,
        "status": allocation.status,
        "startDate": allocation.start_date.isoformat() if allocation.start_date else None,
        "endDate": allocation.end_date.isoformat() if allocation.end_date else None,
        "monthlyFeeMinor": allocation.monthly_fee_minor,
        "paymentStatus": allocation.payment_status,
        "allocatedBy": str(allocation.allocated_by) if allocation.allocated_by else None,
        "allocatedAt": allocation.allocated_at.isoformat() if allocation.allocated_at else None,
        "revokedAt": allocation.revoked_at.isoformat() if allocation.revoked_at else None,
        "revokeReason": allocation.revoke_reason,
        "transferredFromAllocationId": (
            str(allocation.transferred_from_allocation_id)
            if allocation.transferred_from_allocation_id
            else None
        ),
        "metadata": allocation.metadata_json or {},
        "notes": allocation.notes,
        "isActive": allocation.is_active,
        "version": allocation.version,
        "createdAt": allocation.created_at.isoformat() if allocation.created_at else None,
        "updatedAt": allocation.updated_at.isoformat() if allocation.updated_at else None,
    }


def visitor_log_to_dict(log: VisitorParkingLog) -> Dict[str, Any]:
    return {
        "id": str(log.id),
        "societyId": str(log.society_id),
        "slotId": str(log.slot_id) if log.slot_id else None,
        "visitId": str(log.visit_id) if log.visit_id else None,
        "visitorId": str(log.visitor_id) if log.visitor_id else None,
        "residentId": str(log.resident_id) if log.resident_id else None,
        "vehicleNumber": log.vehicle_number,
        "vehicleType": log.vehicle_type,
        "parkingCode": log.parking_code,
        "status": log.status,
        "entryAt": log.entry_at.isoformat() if log.entry_at else None,
        "exitAt": log.exit_at.isoformat() if log.exit_at else None,
        "entryBy": str(log.entry_by) if log.entry_by else None,
        "exitBy": str(log.exit_by) if log.exit_by else None,
        "feeMinor": log.fee_minor,
        "paymentStatus": log.payment_status,
        "purpose": log.purpose,
        "metadata": log.metadata_json or {},
        "notes": log.notes,
        "createdAt": log.created_at.isoformat() if log.created_at else None,
        "updatedAt": log.updated_at.isoformat() if log.updated_at else None,
    }
