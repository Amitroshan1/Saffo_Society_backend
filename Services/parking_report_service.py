"""Parking Management reports (Phase 14)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import cast, Date, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.parking import (
    ParkingAllocation,
    ParkingSlot,
    ParkingZone,
    ResidentVehicle,
    VisitorParkingLog,
)
from Services.parking_helpers import require_society_id
from Utils.errors import ApiError

REPORT_KEYS = {
    "occupancy",
    "available_slots",
    "allocated_slots",
    "visitor_parking",
    "revenue",
    "vehicle_type_summary",
    "reserved_utilization",
    "monthly_statistics",
}


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label} date") from exc


async def run_report(
    db: AsyncSession,
    report_key: str,
    *,
    actor_society_id: UUID | None,
    filters: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    key = report_key.strip().lower().replace("-", "_")
    if key not in REPORT_KEYS:
        raise ApiError(404, f"Unknown report: {report_key}")

    handlers = {
        "occupancy": _occupancy,
        "available_slots": _available_slots,
        "allocated_slots": _allocated_slots,
        "visitor_parking": _visitor_parking,
        "revenue": _revenue,
        "vehicle_type_summary": _vehicle_type_summary,
        "reserved_utilization": _reserved_utilization,
        "monthly_statistics": _monthly_statistics,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


async def _occupancy(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    zones = (
        await db.execute(
            select(ParkingZone).where(
                ParkingZone.society_id == society_id, ParkingZone.is_active.is_(True)
            )
        )
    ).scalars().all()
    result = []
    for zone in zones:
        total = zone.total_slots or 0
        available = zone.available_slots or 0
        occupied = max(0, total - available)
        result.append(
            {
                "zoneId": str(zone.id),
                "zoneName": zone.name,
                "zoneCode": zone.code,
                "totalSlots": total,
                "availableSlots": available,
                "occupiedSlots": occupied,
                "occupancyRate": round((occupied / total) * 100, 2) if total else 0.0,
            }
        )
    return result


async def _available_slots(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(ParkingSlot, ParkingZone.name)
            .join(ParkingZone, ParkingZone.id == ParkingSlot.zone_id)
            .where(
                ParkingSlot.society_id == society_id,
                ParkingSlot.status == "available",
                ParkingSlot.is_active.is_(True),
            )
            .order_by(ParkingSlot.slot_code.asc())
        )
    ).all()
    return [
        {
            "slotId": str(slot.id),
            "slotCode": slot.slot_code,
            "zoneName": zone_name,
            "slotCategory": slot.slot_category,
            "isEvCharging": slot.is_ev_charging,
        }
        for slot, zone_name in rows
    ]


async def _allocated_slots(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(ParkingAllocation, ParkingSlot.slot_code)
            .join(ParkingSlot, ParkingSlot.id == ParkingAllocation.slot_id)
            .where(
                ParkingAllocation.society_id == society_id,
                ParkingAllocation.status == "active",
            )
            .order_by(ParkingAllocation.allocated_at.desc().nullslast())
        )
    ).all()
    return [
        {
            "allocationId": str(a.id),
            "allocationNumber": a.allocation_number,
            "slotCode": slot_code,
            "residentId": str(a.resident_id),
            "allocationType": a.allocation_type,
            "startDate": a.start_date.isoformat() if a.start_date else None,
            "monthlyFeeMinor": a.monthly_fee_minor,
            "paymentStatus": a.payment_status,
        }
        for a, slot_code in rows
    ]


async def _visitor_parking(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = select(VisitorParkingLog).where(VisitorParkingLog.society_id == society_id)
    if from_d:
        stmt = stmt.where(cast(VisitorParkingLog.created_at, Date) >= from_d)
    if to_d:
        stmt = stmt.where(cast(VisitorParkingLog.created_at, Date) <= to_d)
    rows = (await db.execute(stmt.order_by(VisitorParkingLog.created_at.desc()))).scalars().all()
    return [
        {
            "logId": str(log.id),
            "vehicleNumber": log.vehicle_number,
            "vehicleType": log.vehicle_type,
            "status": log.status,
            "parkingCode": log.parking_code,
            "feeMinor": log.fee_minor,
            "paymentStatus": log.payment_status,
            "entryAt": log.entry_at.isoformat() if log.entry_at else None,
            "exitAt": log.exit_at.isoformat() if log.exit_at else None,
        }
        for log in rows
    ]


async def _revenue(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")

    alloc_stmt = select(
        func.coalesce(func.sum(ParkingAllocation.monthly_fee_minor), 0),
        func.count(ParkingAllocation.id),
    ).where(
        ParkingAllocation.society_id == society_id,
        ParkingAllocation.payment_status == "paid",
    )
    if from_d:
        alloc_stmt = alloc_stmt.where(ParkingAllocation.start_date >= from_d)
    if to_d:
        alloc_stmt = alloc_stmt.where(ParkingAllocation.start_date <= to_d)
    alloc_total, alloc_count = (await db.execute(alloc_stmt)).one()

    visitor_stmt = select(
        func.coalesce(func.sum(VisitorParkingLog.fee_minor), 0),
        func.count(VisitorParkingLog.id),
    ).where(
        VisitorParkingLog.society_id == society_id,
        VisitorParkingLog.payment_status == "paid",
    )
    if from_d:
        visitor_stmt = visitor_stmt.where(cast(VisitorParkingLog.entry_at, Date) >= from_d)
    if to_d:
        visitor_stmt = visitor_stmt.where(cast(VisitorParkingLog.entry_at, Date) <= to_d)
    visitor_total, visitor_count = (await db.execute(visitor_stmt)).one()

    return [
        {
            "source": "allocations",
            "count": int(alloc_count),
            "revenue": int(alloc_total),
        },
        {
            "source": "visitor_parking",
            "count": int(visitor_count),
            "revenue": int(visitor_total),
        },
        {
            "source": "total",
            "count": int(alloc_count) + int(visitor_count),
            "revenue": int(alloc_total) + int(visitor_total),
        },
    ]


async def _vehicle_type_summary(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(ResidentVehicle.vehicle_type, func.count(ResidentVehicle.id))
            .where(
                ResidentVehicle.society_id == society_id,
                ResidentVehicle.status == "active",
            )
            .group_by(ResidentVehicle.vehicle_type)
            .order_by(func.count(ResidentVehicle.id).desc())
        )
    ).all()
    return [{"vehicleType": vt, "count": int(cnt)} for vt, cnt in rows]


async def _reserved_utilization(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    reserved_slots = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.society_id == society_id,
                    ParkingSlot.slot_category == "reserved",
                    ParkingSlot.is_active.is_(True),
                )
            )
        ).scalar_one()
    )
    reserved_allocated = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ParkingAllocation)
                .join(ParkingSlot, ParkingSlot.id == ParkingAllocation.slot_id)
                .where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.status == "active",
                    ParkingSlot.slot_category == "reserved",
                )
            )
        ).scalar_one()
    )
    reserved_type_alloc = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.status == "active",
                    ParkingAllocation.allocation_type == "reserved",
                )
            )
        ).scalar_one()
    )
    return [
        {
            "reservedSlots": reserved_slots,
            "reservedSlotsAllocated": reserved_allocated,
            "reservedTypeAllocations": reserved_type_alloc,
            "utilizationRate": (
                round((reserved_allocated / reserved_slots) * 100, 2) if reserved_slots else 0.0
            ),
        }
    ]


async def _monthly_statistics(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    year = date.today().year
    year_filter = filters.get("year")
    if year_filter:
        try:
            year = int(year_filter)
        except ValueError as exc:
            raise ApiError(422, "Invalid year") from exc

    alloc_rows = (
        await db.execute(
            select(
                extract("month", ParkingAllocation.start_date),
                func.count(ParkingAllocation.id),
                func.coalesce(func.sum(ParkingAllocation.monthly_fee_minor), 0),
            )
            .where(
                ParkingAllocation.society_id == society_id,
                extract("year", ParkingAllocation.start_date) == year,
            )
            .group_by(extract("month", ParkingAllocation.start_date))
            .order_by(extract("month", ParkingAllocation.start_date))
        )
    ).all()

    visitor_rows = (
        await db.execute(
            select(
                extract("month", VisitorParkingLog.entry_at),
                func.count(VisitorParkingLog.id),
            )
            .where(
                VisitorParkingLog.society_id == society_id,
                VisitorParkingLog.entry_at.isnot(None),
                extract("year", VisitorParkingLog.entry_at) == year,
            )
            .group_by(extract("month", VisitorParkingLog.entry_at))
            .order_by(extract("month", VisitorParkingLog.entry_at))
        )
    ).all()

    by_month: Dict[int, dict] = {}
    for month, cnt, revenue in alloc_rows:
        m = int(month)
        by_month[m] = {
            "year": year,
            "month": m,
            "allocations": int(cnt),
            "allocationRevenue": int(revenue),
            "visitorEntries": 0,
        }
    for month, cnt in visitor_rows:
        m = int(month)
        if m not in by_month:
            by_month[m] = {
                "year": year,
                "month": m,
                "allocations": 0,
                "allocationRevenue": 0,
                "visitorEntries": 0,
            }
        by_month[m]["visitorEntries"] = int(cnt)

    return [by_month[m] for m in sorted(by_month.keys())]
