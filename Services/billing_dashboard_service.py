"""Billing dashboard KPIs."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.flat import Flat
from Models.maintenance_bill import MaintenanceBill
from Models.payment import Payment
from Models.resident import Resident
from Services.billing_helpers import require_society_id


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end = datetime.combine(d, time.max, tzinfo=timezone.utc)
    return start, end


async def get_dashboard(
    db: AsyncSession, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()
    month_start = date(today.year, today.month, 1)
    today_start, today_end = _day_bounds(today)
    month_start_dt = datetime.combine(month_start, time.min, tzinfo=timezone.utc)

    today_collection = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                    Payment.society_id == society_id,
                    Payment.status == "cleared",
                    Payment.payment_date >= today_start,
                    Payment.payment_date <= today_end,
                )
            )
        ).scalar_one()
        or 0
    )
    month_collection = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                    Payment.society_id == society_id,
                    Payment.status == "cleared",
                    Payment.payment_date >= month_start_dt,
                )
            )
        ).scalar_one()
        or 0
    )
    total_outstanding = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(MaintenanceBill.outstanding_minor), 0)).where(
                    MaintenanceBill.society_id == society_id,
                    MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
                    MaintenanceBill.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    overdue_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(MaintenanceBill.outstanding_minor), 0),
                func.count(MaintenanceBill.id),
            ).where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status == "overdue",
                MaintenanceBill.is_active.is_(True),
            )
        )
    ).one()
    overdue_amount = int(overdue_row[0] or 0)
    overdue_count = int(overdue_row[1] or 0)

    defaulter_rows = (
        await db.execute(
            select(
                MaintenanceBill.resident_id,
                MaintenanceBill.flat_id,
                func.sum(MaintenanceBill.outstanding_minor).label("outstanding"),
            )
            .where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
                MaintenanceBill.outstanding_minor > 0,
                MaintenanceBill.is_active.is_(True),
            )
            .group_by(MaintenanceBill.resident_id, MaintenanceBill.flat_id)
            .order_by(func.sum(MaintenanceBill.outstanding_minor).desc())
            .limit(10)
        )
    ).all()
    resident_ids = {r[0] for r in defaulter_rows}
    flat_ids = {r[1] for r in defaulter_rows}
    residents = {}
    if resident_ids:
        residents = {
            x.id: x
            for x in (
                await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
            ).scalars().all()
        }
    flats = {}
    if flat_ids:
        flats = {
            x.id: x
            for x in (await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))).scalars().all()
        }
    top_defaulters = [
        {
            "residentId": str(rid),
            "residentName": residents[rid].name if rid in residents else None,
            "flatId": str(fid),
            "flatNo": flats[fid].flat_no if fid in flats else None,
            "outstandingMinor": int(amt or 0),
        }
        for rid, fid, amt in defaulter_rows
    ]

    mode_rows = (
        await db.execute(
            select(Payment.mode, func.coalesce(func.sum(Payment.amount_minor), 0))
            .where(
                Payment.society_id == society_id,
                Payment.status == "cleared",
                Payment.payment_date >= month_start_dt,
            )
            .group_by(Payment.mode)
        )
    ).all()
    collection_by_mode = [
        {"mode": mode, "amountMinor": int(amt or 0)} for mode, amt in mode_rows
    ]

    return {
        "todayCollectionMinor": today_collection,
        "monthCollectionMinor": month_collection,
        "totalOutstandingMinor": total_outstanding,
        "overdueAmountMinor": overdue_amount,
        "overdueCount": overdue_count,
        "topDefaulters": top_defaulters,
        "collectionByMode": collection_by_mode,
    }
