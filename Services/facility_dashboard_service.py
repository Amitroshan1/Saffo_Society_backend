"""Amenities Booking dashboard KPIs (Phase 13)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.facility import Facility, FacilityBooking
from Services.facility_helpers import require_society_id


async def get_dashboard(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()
    month_start = today.replace(day=1)

    async def _count(*clauses) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(Facility.society_id == society_id, *clauses)
                )
            ).scalar_one()
        )

    total_amenities = await _count(Facility.is_active.is_(True))
    active_amenities = await _count(Facility.status == "active")

    today_bookings = int(
        (
            await db.execute(
                select(func.count()).where(
                    FacilityBooking.society_id == society_id,
                    FacilityBooking.booking_date == today,
                    FacilityBooking.status.notin_(("cancelled", "rejected")),
                )
            )
        ).scalar_one()
    )

    pending_approvals = int(
        (
            await db.execute(
                select(func.count()).where(
                    FacilityBooking.society_id == society_id, FacilityBooking.status == "pending"
                )
            )
        ).scalar_one()
    )

    revenue_this_month = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(FacilityBooking.amount), 0)).where(
                    FacilityBooking.society_id == society_id,
                    FacilityBooking.payment_status == "paid",
                    FacilityBooking.booking_date >= month_start,
                    FacilityBooking.booking_date <= today,
                )
            )
        ).scalar_one()
    )

    popular_rows = (
        await db.execute(
            select(Facility.id, Facility.name, func.count(FacilityBooking.id))
            .join(FacilityBooking, FacilityBooking.amenity_id == Facility.id)
            .where(
                Facility.society_id == society_id,
                FacilityBooking.status.notin_(("cancelled", "rejected")),
            )
            .group_by(Facility.id, Facility.name)
            .order_by(func.count(FacilityBooking.id).desc())
            .limit(5)
        )
    ).all()
    popular_amenities = [
        {"amenityId": str(aid), "amenityName": name, "bookingCount": int(cnt)}
        for aid, name, cnt in popular_rows
    ]

    by_status_rows = (
        await db.execute(
            select(FacilityBooking.status, func.count(FacilityBooking.id))
            .where(FacilityBooking.society_id == society_id)
            .group_by(FacilityBooking.status)
        )
    ).all()
    bookings_by_status = [{"status": status, "count": int(cnt)} for status, cnt in by_status_rows]

    capacity_total = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Facility.capacity), 0)).where(
                    Facility.society_id == society_id, Facility.status == "active"
                )
            )
        ).scalar_one()
    )
    occupancy_rate = round((today_bookings / capacity_total) * 100, 2) if capacity_total else 0.0

    return {
        "totalAmenities": total_amenities,
        "activeAmenities": active_amenities,
        "todayBookings": today_bookings,
        "pendingApprovals": pending_approvals,
        "revenueThisMonth": revenue_this_month,
        "popularAmenities": popular_amenities,
        "bookingsByStatus": bookings_by_status,
        "occupancyRate": occupancy_rate,
    }
