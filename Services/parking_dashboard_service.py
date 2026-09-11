"""Parking Management dashboard KPIs (Phase 14)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict
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
from Services.parking_helpers import require_society_id


async def get_dashboard(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()
    month_start = today.replace(day=1)

    total_zones = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingZone.society_id == society_id, ParkingZone.is_active.is_(True)
                )
            )
        ).scalar_one()
    )
    total_slots = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.society_id == society_id, ParkingSlot.is_active.is_(True)
                )
            )
        ).scalar_one()
    )
    available_slots = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.society_id == society_id,
                    ParkingSlot.is_active.is_(True),
                    ParkingSlot.status == "available",
                )
            )
        ).scalar_one()
    )
    allocated_slots = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.society_id == society_id,
                    ParkingSlot.status.in_(("allocated", "reserved", "occupied")),
                )
            )
        ).scalar_one()
    )
    occupied_now = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingSlot.society_id == society_id,
                    ParkingSlot.status.in_(("occupied", "visitor")),
                )
            )
        ).scalar_one()
    )
    active_allocations = int(
        (
            await db.execute(
                select(func.count()).where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.status == "active",
                )
            )
        ).scalar_one()
    )
    registered_vehicles = int(
        (
            await db.execute(
                select(func.count()).where(
                    ResidentVehicle.society_id == society_id,
                    ResidentVehicle.status == "active",
                )
            )
        ).scalar_one()
    )
    active_visitors = int(
        (
            await db.execute(
                select(func.count()).where(
                    VisitorParkingLog.society_id == society_id,
                    VisitorParkingLog.status == "active",
                )
            )
        ).scalar_one()
    )
    revenue_this_month = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(ParkingAllocation.monthly_fee_minor), 0)).where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.payment_status == "paid",
                    ParkingAllocation.start_date >= month_start,
                    ParkingAllocation.start_date <= today,
                )
            )
        ).scalar_one()
    )

    by_status = (
        await db.execute(
            select(ParkingSlot.status, func.count(ParkingSlot.id))
            .where(ParkingSlot.society_id == society_id, ParkingSlot.is_active.is_(True))
            .group_by(ParkingSlot.status)
        )
    ).all()
    slots_by_status = [{"status": s, "count": int(c)} for s, c in by_status]

    occupancy_rate = (
        round(((total_slots - available_slots) / total_slots) * 100, 2) if total_slots else 0.0
    )

    return {
        "totalZones": total_zones,
        "totalSlots": total_slots,
        "availableSlots": available_slots,
        "allocatedSlots": allocated_slots,
        "occupiedNow": occupied_now,
        "activeAllocations": active_allocations,
        "registeredVehicles": registered_vehicles,
        "activeVisitorParking": active_visitors,
        "revenueThisMonth": revenue_this_month,
        "occupancyRate": occupancy_rate,
        "slotsByStatus": slots_by_status,
    }
