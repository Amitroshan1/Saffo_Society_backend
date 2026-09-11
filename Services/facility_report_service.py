"""Amenities Booking reports (Phase 13)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.facility import Facility, FacilityBooking, FacilityMaintenanceBlock
from Models.resident import Resident
from Services.facility_helpers import require_society_id
from Utils.errors import ApiError

REPORT_KEYS = {
    "booking_summary",
    "revenue_summary",
    "popular_amenities",
    "peak_hours",
    "cancelled_bookings",
    "maintenance_utilization",
    "resident_usage",
    "amenity_occupancy",
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
        "booking_summary": _booking_summary,
        "revenue_summary": _revenue_summary,
        "popular_amenities": _popular_amenities,
        "peak_hours": _peak_hours,
        "cancelled_bookings": _cancelled_bookings,
        "maintenance_utilization": _maintenance_utilization,
        "resident_usage": _resident_usage,
        "amenity_occupancy": _amenity_occupancy,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


def _date_range_clauses(filters: Dict[str, Optional[str]]):
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    clauses = []
    if from_d:
        clauses.append(FacilityBooking.booking_date >= from_d)
    if to_d:
        clauses.append(FacilityBooking.booking_date <= to_d)
    return clauses


async def _booking_summary(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(FacilityBooking.status, func.count(FacilityBooking.id))
        .where(FacilityBooking.society_id == society_id, *_date_range_clauses(filters))
        .group_by(FacilityBooking.status)
    )
    rows = (await db.execute(stmt)).all()
    return [{"status": status, "count": int(cnt)} for status, cnt in rows]


async def _revenue_summary(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(
            Facility.id,
            Facility.name,
            func.count(FacilityBooking.id),
            func.coalesce(func.sum(FacilityBooking.amount), 0),
        )
        .join(FacilityBooking, FacilityBooking.amenity_id == Facility.id)
        .where(
            Facility.society_id == society_id,
            FacilityBooking.payment_status == "paid",
            *_date_range_clauses(filters),
        )
        .group_by(Facility.id, Facility.name)
        .order_by(func.coalesce(func.sum(FacilityBooking.amount), 0).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"amenityId": str(aid), "amenityName": name, "bookingCount": int(cnt), "revenue": int(total)}
        for aid, name, cnt, total in rows
    ]


async def _popular_amenities(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(Facility.id, Facility.name, Facility.category, func.count(FacilityBooking.id))
        .join(FacilityBooking, FacilityBooking.amenity_id == Facility.id)
        .where(
            Facility.society_id == society_id,
            FacilityBooking.status.notin_(("cancelled", "rejected")),
            *_date_range_clauses(filters),
        )
        .group_by(Facility.id, Facility.name, Facility.category)
        .order_by(func.count(FacilityBooking.id).desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"amenityId": str(aid), "amenityName": name, "category": category, "bookingCount": int(cnt)}
        for aid, name, category, cnt in rows
    ]


async def _peak_hours(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(FacilityBooking.start_time, func.count(FacilityBooking.id))
        .where(
            FacilityBooking.society_id == society_id,
            FacilityBooking.status.notin_(("cancelled", "rejected")),
            *_date_range_clauses(filters),
        )
        .group_by(FacilityBooking.start_time)
        .order_by(func.count(FacilityBooking.id).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"startTime": start_time, "bookingCount": int(cnt)} for start_time, cnt in rows]


async def _cancelled_bookings(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(FacilityBooking, Facility.name)
        .join(Facility, Facility.id == FacilityBooking.amenity_id)
        .where(
            FacilityBooking.society_id == society_id,
            FacilityBooking.status.in_(("cancelled", "rejected")),
            *_date_range_clauses(filters),
        )
        .order_by(FacilityBooking.cancelled_at.desc().nullslast())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "bookingId": str(b.id),
            "bookingNumber": b.booking_number,
            "amenityName": name,
            "status": b.status,
            "bookingDate": b.booking_date.isoformat() if b.booking_date else None,
            "cancelledAt": b.cancelled_at.isoformat() if b.cancelled_at else None,
            "reason": b.cancellation_reason or b.rejected_reason,
        }
        for b, name in rows
    ]


async def _maintenance_utilization(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = (
        select(FacilityMaintenanceBlock, Facility.name)
        .join(Facility, Facility.id == FacilityMaintenanceBlock.amenity_id)
        .where(FacilityMaintenanceBlock.society_id == society_id)
    )
    if from_d:
        stmt = stmt.where(FacilityMaintenanceBlock.end_date >= from_d)
    if to_d:
        stmt = stmt.where(FacilityMaintenanceBlock.start_date <= to_d)
    rows = (await db.execute(stmt.order_by(FacilityMaintenanceBlock.start_date.desc()))).all()
    return [
        {
            "amenityName": name,
            "startDate": block.start_date.isoformat(),
            "endDate": block.end_date.isoformat(),
            "days": (block.end_date - block.start_date).days + 1,
            "reason": block.reason,
            "isActive": block.is_active,
        }
        for block, name in rows
    ]


async def _resident_usage(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    stmt = (
        select(Resident.id, Resident.name, Resident.code, func.count(FacilityBooking.id))
        .join(FacilityBooking, FacilityBooking.resident_id == Resident.id)
        .where(
            FacilityBooking.society_id == society_id,
            FacilityBooking.status.notin_(("cancelled", "rejected")),
            *_date_range_clauses(filters),
        )
        .group_by(Resident.id, Resident.name, Resident.code)
        .order_by(func.count(FacilityBooking.id).desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"residentId": str(rid), "residentName": name, "residentCode": code, "bookingCount": int(cnt)}
        for rid, name, code, cnt in rows
    ]


async def _amenity_occupancy(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    amenities = (
        await db.execute(
            select(Facility).where(Facility.society_id == society_id, Facility.status == "active")
        )
    ).scalars().all()

    result = []
    for amenity in amenities:
        stmt = select(func.count()).where(
            FacilityBooking.amenity_id == amenity.id,
            FacilityBooking.status.notin_(("cancelled", "rejected")),
            *_date_range_clauses(filters),
        )
        booking_count = int((await db.execute(stmt)).scalar_one())
        result.append(
            {
                "amenityId": str(amenity.id),
                "amenityName": amenity.name,
                "capacity": amenity.capacity,
                "bookingCount": booking_count,
            }
        )
    return result
