"""Guard parking portal — today board, entry/exit, visitor parking."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.parking import (
    ParkingAllocation,
    ParkingSlot,
    ResidentVehicle,
    VisitorParkingLog,
)
from Models.resident import Resident
from Schemas.parking import (
    ParkingEntryRequest,
    ParkingExitRequest,
    VisitorParkingCreate,
    VisitorParkingListQueryParams,
)
from Services import parking_service
from Services.parking_helpers import (
    ACTIVE_ALLOCATION_STATUS,
    ensure_visitor_parking_allowed,
    get_slot_in_society,
    get_visitor_log_in_society,
    get_zone_in_society,
    refresh_zone_slot_counts,
    require_society_id,
    slot_to_dict,
    vehicle_to_dict,
    visitor_log_to_dict,
)
from Utils.audit import apply_update_audit, utcnow
from Utils.errors import ApiError


async def create_visitor_parking(
    db: AsyncSession,
    body: VisitorParkingCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await parking_service.create_visitor_parking(
        db,
        body,
        actor_id=actor_id,
        actor_society_id=actor_society_id,
        auto_entry=True,
    )


async def guard_today(
    db: AsyncSession, query: VisitorParkingListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()

    occupied_slots = (
        await db.execute(
            select(ParkingSlot).where(
                ParkingSlot.society_id == society_id,
                ParkingSlot.status.in_(("occupied", "visitor")),
            )
        )
    ).scalars().all()

    visitor_base = select(VisitorParkingLog).where(
        VisitorParkingLog.society_id == society_id,
        VisitorParkingLog.status.in_(("requested", "active")),
    )
    if query.status:
        visitor_base = visitor_base.where(VisitorParkingLog.status == query.status)
    visitors = (
        await db.execute(visitor_base.order_by(VisitorParkingLog.created_at.desc()).limit(100))
    ).scalars().all()

    allocations = (
        await db.execute(
            select(ParkingAllocation).where(
                ParkingAllocation.society_id == society_id,
                ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
            )
        )
    ).scalars().all()

    alloc_ids = [s.current_allocation_id for s in occupied_slots if s.current_allocation_id]
    alloc_by_id: Dict[UUID, ParkingAllocation] = {}
    vehicle_by_id: Dict[UUID, ResidentVehicle] = {}
    resident_by_id: Dict[UUID, Resident] = {}
    if alloc_ids:
        alloc_rows = (
            await db.execute(select(ParkingAllocation).where(ParkingAllocation.id.in_(alloc_ids)))
        ).scalars().all()
        alloc_by_id = {a.id: a for a in alloc_rows}
        vehicle_ids = [a.vehicle_id for a in alloc_rows if a.vehicle_id]
        resident_ids = [a.resident_id for a in alloc_rows if a.resident_id]
        if vehicle_ids:
            vehicle_by_id = {
                v.id: v
                for v in (
                    await db.execute(select(ResidentVehicle).where(ResidentVehicle.id.in_(vehicle_ids)))
                ).scalars().all()
            }
        if resident_ids:
            resident_by_id = {
                r.id: r
                for r in (
                    await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
                ).scalars().all()
            }

    slot_by_id = {s.id: s for s in occupied_slots}
    parked: list[Dict[str, Any]] = []
    used_slot_ids: set[UUID] = set()

    for log in visitors:
        slot = slot_by_id.get(log.slot_id) if log.slot_id else None
        if log.slot_id:
            used_slot_ids.add(log.slot_id)
        parked.append(
            {
                "id": str(log.id),
                "kind": "visitor",
                "vehicleNumber": log.vehicle_number,
                "vehicleType": log.vehicle_type,
                "residentName": None,
                "parkingCode": log.parking_code,
                "slotCode": slot.slot_code if slot else None,
                "slotStatus": slot.status if slot else None,
                "status": log.status,
                "entryAt": log.entry_at.isoformat() if log.entry_at else None,
            }
        )

    for slot in occupied_slots:
        if slot.id in used_slot_ids:
            continue
        alloc = alloc_by_id.get(slot.current_allocation_id) if slot.current_allocation_id else None
        vehicle = vehicle_by_id.get(alloc.vehicle_id) if alloc and alloc.vehicle_id else None
        resident = resident_by_id.get(alloc.resident_id) if alloc else None
        parked.append(
            {
                "id": str(slot.id),
                "kind": "resident",
                "vehicleNumber": vehicle.vehicle_number if vehicle else None,
                "vehicleType": vehicle.vehicle_type if vehicle else None,
                "residentName": resident.name if resident else None,
                "parkingCode": vehicle.parking_code if vehicle else None,
                "slotCode": slot.slot_code,
                "slotStatus": slot.status,
                "status": slot.status,
                "entryAt": None,
            }
        )

    resident_vehicles = (
        await db.execute(
            select(ResidentVehicle).where(
                ResidentVehicle.society_id == society_id,
                ResidentVehicle.is_active.is_(True),
                ResidentVehicle.parking_code.isnot(None),
            )
        )
    ).scalars().all()

    parking_codes: list[Dict[str, Any]] = []
    seen_codes: set[str] = set()

    for vehicle in resident_vehicles:
        code = (vehicle.parking_code or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        parking_codes.append(
            {
                "code": code,
                "vehicleNumber": vehicle.vehicle_number,
                "vehicleType": vehicle.vehicle_type,
                "kind": "resident",
                "label": f"{code} · {vehicle.vehicle_number}",
            }
        )

    for log in visitors:
        code = (log.parking_code or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        parking_codes.append(
            {
                "code": code,
                "vehicleNumber": log.vehicle_number,
                "vehicleType": log.vehicle_type,
                "kind": "visitor",
                "label": f"{code} · {log.vehicle_number} (visitor)",
            }
        )

    parking_codes.sort(key=lambda row: row["code"])

    all_slots = (
        await db.execute(
            select(ParkingSlot).where(
                ParkingSlot.society_id == society_id,
                ParkingSlot.is_active.is_(True),
            ).order_by(ParkingSlot.slot_code.asc())
        )
    ).scalars().all()

    parked_by_slot = {row["slotCode"]: row for row in parked if row.get("slotCode")}
    slots_list: list[Dict[str, Any]] = []
    for slot in all_slots:
        parked_row = parked_by_slot.get(slot.slot_code)
        slots_list.append(
            {
                "id": str(slot.id),
                "code": slot.slot_code,
                "slotCode": slot.slot_code,
                "status": slot.status,
                "vehicleNumber": parked_row.get("vehicleNumber") if parked_row else None,
                "kind": parked_row.get("kind") if parked_row else "slot",
                "label": (
                    f"{slot.slot_code} · {parked_row['vehicleNumber']}"
                    if parked_row and parked_row.get("vehicleNumber")
                    else f"{slot.slot_code} · {slot.status}"
                ),
            }
        )

    return {
        "date": today.isoformat(),
        "occupiedSlots": [slot_to_dict(s) for s in occupied_slots],
        "activeVisitorParking": [visitor_log_to_dict(v) for v in visitors],
        "activeAllocationsCount": len(allocations),
        "parkedVehicles": parked,
        "parkingCodes": parking_codes,
        "slots": slots_list,
        "vehicles": parked,
    }


async def vehicle_entry(
    db: AsyncSession,
    body: ParkingEntryRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    now = utcnow()

    visitor_log = None
    if body.parkingCode:
        visitor_log = (
            await db.execute(
                select(VisitorParkingLog).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.parking_code == body.parkingCode,
                    VisitorParkingLog.status.in_(("requested", "active")),
                )
            )
        ).scalar_one_or_none()
    if not visitor_log and body.vehicleNumber:
        visitor_log = (
            await db.execute(
                select(VisitorParkingLog).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.vehicle_number == body.vehicleNumber,
                    VisitorParkingLog.status.in_(("requested", "active")),
                )
            )
        ).scalar_one_or_none()

    if visitor_log:
        if visitor_log.status == "active" and visitor_log.entry_at:
            raise ApiError(422, "Visitor vehicle already entered")
        visitor_log.status = "active"
        visitor_log.entry_at = now
        visitor_log.entry_by = actor_id
        if body.notes:
            visitor_log.notes = body.notes
        slot = None
        if body.slotId:
            slot = await get_slot_in_society(db, body.slotId, society_id)
            visitor_log.slot_id = slot.id
        elif visitor_log.slot_id:
            slot = await get_slot_in_society(db, visitor_log.slot_id, society_id)
        if slot:
            zone = await get_zone_in_society(db, slot.zone_id, society_id)
            ensure_visitor_parking_allowed(zone, slot)
            slot.status = "visitor"
            apply_update_audit(slot, actor_id)
            await refresh_zone_slot_counts(db, zone)
        await db.commit()
        publish_simple(
            "VehicleEntry",
            society_id=society_id,
            entity_type="visitor_parking_log",
            entity_id=visitor_log.id,
            actor_id=actor_id,
            payload={"logId": str(visitor_log.id), "type": "visitor"},
        )
        return {"entry": visitor_log_to_dict(visitor_log), "type": "visitor"}

    vehicle = None
    if body.parkingCode:
        vehicle = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.parking_code == body.parkingCode,
                    ResidentVehicle.status == "active",
                )
            )
        ).scalar_one_or_none()
    if not vehicle and body.vehicleNumber:
        vehicle = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.vehicle_number == body.vehicleNumber,
                    ResidentVehicle.status == "active",
                )
            )
        ).scalar_one_or_none()

    slot = None
    if body.slotId:
        slot = await get_slot_in_society(db, body.slotId, society_id)
    elif vehicle:
        allocation = (
            await db.execute(
                select(ParkingAllocation).where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.vehicle_id == vehicle.id,
                    ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
                )
            )
        ).scalar_one_or_none()
        if allocation:
            slot = await get_slot_in_society(db, allocation.slot_id, society_id)

    if not slot:
        raise ApiError(404, "No matching vehicle or parking slot found for entry")

    if slot.status in ("maintenance", "blocked", "inactive"):
        raise ApiError(422, f"Slot is {slot.status}")

    slot.status = "occupied"
    apply_update_audit(slot, actor_id)
    zone = await get_zone_in_society(db, slot.zone_id, society_id)
    await refresh_zone_slot_counts(db, zone)
    await db.commit()

    publish_simple(
        "VehicleEntry",
        society_id=society_id,
        entity_type="parking_slot",
        entity_id=slot.id,
        actor_id=actor_id,
        payload={
            "slotId": str(slot.id),
            "vehicleId": str(vehicle.id) if vehicle else None,
            "type": "resident",
        },
    )
    return {
        "entry": {
            "slot": slot_to_dict(slot, zone=zone),
            "vehicle": vehicle_to_dict(vehicle) if vehicle else None,
            "enteredAt": now.isoformat(),
        },
        "type": "resident",
    }


async def vehicle_exit(
    db: AsyncSession,
    body: ParkingExitRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    now = utcnow()

    visitor_log = None
    if body.visitorLogId:
        visitor_log = await get_visitor_log_in_society(db, body.visitorLogId, society_id)
    elif body.parkingCode:
        visitor_log = (
            await db.execute(
                select(VisitorParkingLog).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.parking_code == body.parkingCode,
                    VisitorParkingLog.status == "active",
                )
            )
        ).scalar_one_or_none()
    elif body.vehicleNumber:
        visitor_log = (
            await db.execute(
                select(VisitorParkingLog).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.vehicle_number == body.vehicleNumber,
                    VisitorParkingLog.status == "active",
                )
            )
        ).scalar_one_or_none()
    if not visitor_log and body.slotId:
        visitor_log = (
            await db.execute(
                select(VisitorParkingLog).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.slot_id == body.slotId,
                    VisitorParkingLog.status == "active",
                )
            )
        ).scalar_one_or_none()

    if visitor_log:
        if visitor_log.status != "active":
            raise ApiError(422, "Visitor parking is not active")
        visitor_log.status = "exited"
        visitor_log.exit_at = now
        visitor_log.exit_by = actor_id
        if body.notes:
            visitor_log.notes = body.notes
        if visitor_log.slot_id:
            slot = await get_slot_in_society(db, visitor_log.slot_id, society_id)
            slot.status = "available"
            apply_update_audit(slot, actor_id)
            zone = await get_zone_in_society(db, slot.zone_id, society_id)
            await refresh_zone_slot_counts(db, zone)
        await db.commit()
        publish_simple(
            "VehicleExit",
            society_id=society_id,
            entity_type="visitor_parking_log",
            entity_id=visitor_log.id,
            actor_id=actor_id,
            payload={"logId": str(visitor_log.id), "type": "visitor"},
        )
        return {"exit": visitor_log_to_dict(visitor_log), "type": "visitor"}

    slot = None
    if body.slotId:
        slot = await get_slot_in_society(db, body.slotId, society_id)
    elif body.parkingCode:
        vehicle = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.parking_code == body.parkingCode,
                )
            )
        ).scalar_one_or_none()
        if vehicle:
            allocation = (
                await db.execute(
                    select(ParkingAllocation).where(
                        ParkingAllocation.vehicle_id == vehicle.id,
                        ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
                    )
                )
            ).scalar_one_or_none()
            if allocation:
                slot = await get_slot_in_society(db, allocation.slot_id, society_id)
    elif body.vehicleNumber:
        vehicle = (
            await db.execute(
                select(ResidentVehicle).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.vehicle_number == body.vehicleNumber,
                    ResidentVehicle.status == "active",
                )
            )
        ).scalar_one_or_none()
        if vehicle:
            allocation = (
                await db.execute(
                    select(ParkingAllocation).where(
                        ParkingAllocation.vehicle_id == vehicle.id,
                        ParkingAllocation.status == ACTIVE_ALLOCATION_STATUS,
                    )
                )
            ).scalar_one_or_none()
            if allocation:
                slot = await get_slot_in_society(db, allocation.slot_id, society_id)

    if not slot:
        raise ApiError(404, "No matching parking record found for exit")
    if slot.status not in ("occupied", "visitor"):
        raise ApiError(422, "Slot is not currently occupied")

    if slot.current_allocation_id:
        slot.status = "allocated"
    else:
        slot.status = "available"
    apply_update_audit(slot, actor_id)
    zone = await get_zone_in_society(db, slot.zone_id, society_id)
    await refresh_zone_slot_counts(db, zone)
    await db.commit()

    publish_simple(
        "VehicleExit",
        society_id=society_id,
        entity_type="parking_slot",
        entity_id=slot.id,
        actor_id=actor_id,
        payload={"slotId": str(slot.id), "type": "resident"},
    )
    return {
        "exit": {"slot": slot_to_dict(slot, zone=zone), "exitedAt": now.isoformat()},
        "type": "resident",
    }
