"""Phase 16 analytics engines — aggregation, KPI, reports, dashboards, exports, schedules."""

from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.facility import FacilityBooking
from Models.analytics import (
    AnalyticsDailyFact,
    AnalyticsDashboardLayout,
    AnalyticsExportDownload,
    AnalyticsExportJob,
    AnalyticsKpiDefinition,
    AnalyticsKpiSnapshot,
    AnalyticsMonthlyFact,
    AnalyticsReportDefinition,
    AnalyticsUserPreference,
    AnalyticsAccessLog,
    ReportSchedule,
    ReportScheduleRun,
)
from Models.complaint import Complaint
from Models.document import Document
from Models.flat import Flat
from Models.maintenance_bill import MaintenanceBill
from Models.notice import Notice, NoticeRead
from Models.notification import Notification
from Models.occupancy import Occupancy
from Models.parking import ParkingAllocation, ParkingSlot
from Models.payment import Payment
from Models.resident import Resident
from Models.shift import Shift
from Models.visit import Visit
from Services.analytics_helpers import (
    ensure_catalog_seeded,
    iso,
    log_access,
    require_society_id,
    role_allowed,
    serialize_kpi_def,
    serialize_report_def,
)
from Utils.errors import ApiError
from Schemas.common import build_pagination_meta


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end = datetime.combine(d, time.max, tzinfo=timezone.utc)
    return start, end


async def _upsert_daily(
    db: AsyncSession,
    society_id: UUID,
    grain_date: date,
    metric_key: str,
    value: int,
) -> None:
    row = (
        await db.execute(
            select(AnalyticsDailyFact).where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.grain_date == grain_date,
                AnalyticsDailyFact.metric_key == metric_key,
                AnalyticsDailyFact.building_id.is_(None),
                AnalyticsDailyFact.wing_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row:
        row.metric_value = int(value)
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(
            AnalyticsDailyFact(
                society_id=society_id,
                grain_date=grain_date,
                metric_key=metric_key,
                metric_value=int(value),
            )
        )


async def rebuild_society_day(
    db: AsyncSession, society_id: UUID, grain_date: date | None = None
) -> dict[str, int]:
    society_id = require_society_id(society_id)
    grain_date = grain_date or date.today()
    start, end = _day_bounds(grain_date)
    month_start = date(grain_date.year, grain_date.month, 1)
    month_start_dt = datetime.combine(month_start, time.min, tzinfo=timezone.utc)

    total_flats = int(
        (
            await db.execute(
                select(func.count(Flat.id)).where(
                    Flat.society_id == society_id, Flat.is_active.is_(True)
                )
            )
        ).scalar_one()
        or 0
    )
    occupied = int(
        (
            await db.execute(
                select(func.count(func.distinct(Occupancy.flat_id))).where(
                    Occupancy.society_id == society_id,
                    Occupancy.status == "active",
                    Occupancy.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    vacant = max(total_flats - occupied, 0)
    residents = int(
        (
            await db.execute(
                select(func.count(func.distinct(Occupancy.resident_id))).where(
                    Occupancy.society_id == society_id,
                    Occupancy.status == "active",
                    Occupancy.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    revenue_day = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                    Payment.society_id == society_id,
                    Payment.status == "cleared",
                    Payment.payment_date >= start,
                    Payment.payment_date <= end,
                )
            )
        ).scalar_one()
        or 0
    )
    revenue_month = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                    Payment.society_id == society_id,
                    Payment.status == "cleared",
                    Payment.payment_date >= month_start_dt,
                    Payment.payment_date <= end,
                )
            )
        ).scalar_one()
        or 0
    )
    outstanding = int(
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
    overdue = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(MaintenanceBill.outstanding_minor), 0)).where(
                    MaintenanceBill.society_id == society_id,
                    MaintenanceBill.status == "overdue",
                    MaintenanceBill.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    billed_month = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(MaintenanceBill.net_minor), 0)).where(
                    MaintenanceBill.society_id == society_id,
                    MaintenanceBill.is_active.is_(True),
                    MaintenanceBill.created_at >= month_start_dt,
                )
            )
        ).scalar_one()
        or 0
    )
    open_complaints = int(
        (
            await db.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.society_id == society_id,
                    Complaint.status.in_(("open", "in_progress", "pending")),
                    Complaint.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    resolved_month = int(
        (
            await db.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.society_id == society_id,
                    Complaint.status.in_(("resolved", "closed")),
                    Complaint.updated_at >= month_start_dt,
                )
            )
        ).scalar_one()
        or 0
    )
    closed_month = resolved_month
    visitor_day = int(
        (
            await db.execute(
                select(func.count(Visit.id)).where(
                    Visit.society_id == society_id,
                    or_(
                        and_(Visit.check_in_time >= start, Visit.check_in_time <= end),
                        and_(Visit.created_at >= start, Visit.created_at <= end),
                    ),
                )
            )
        ).scalar_one()
        or 0
    )
    parking_total = int(
        (
            await db.execute(
                select(func.count(ParkingSlot.id)).where(
                    ParkingSlot.society_id == society_id, ParkingSlot.is_active.is_(True)
                )
            )
        ).scalar_one()
        or 0
    )
    parking_alloc = int(
        (
            await db.execute(
                select(func.count(ParkingAllocation.id)).where(
                    ParkingAllocation.society_id == society_id,
                    ParkingAllocation.status.in_(("active", "allocated")),
                    ParkingAllocation.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    bookings_day = int(
        (
            await db.execute(
                select(func.count(FacilityBooking.id)).where(
                    FacilityBooking.society_id == society_id,
                    FacilityBooking.booking_date == grain_date,
                )
            )
        ).scalar_one()
        or 0
    )
    unread_notif = int(
        (
            await db.execute(
                select(func.count(Notification.id)).where(
                    Notification.society_id == society_id,
                    Notification.status.in_(("delivered", "queued", "pending")),
                    Notification.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    docs_pub = int(
        (
            await db.execute(
                select(func.count(Document.id)).where(
                    Document.society_id == society_id,
                    Document.status == "published",
                    Document.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    notices_pub = int(
        (
            await db.execute(
                select(func.count(Notice.id)).where(
                    Notice.society_id == society_id,
                    Notice.status == "published",
                    Notice.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )
    notice_reads = int(
        (
            await db.execute(
                select(func.count(NoticeRead.id)).where(NoticeRead.society_id == society_id)
            )
        ).scalar_one()
        or 0
    )
    on_duty = int(
        (
            await db.execute(
                select(func.count(Shift.id)).where(
                    Shift.society_id == society_id,
                    Shift.status == "active",
                    Shift.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    )

    metrics = {
        "occupancy.flats.total": total_flats,
        "occupancy.flats.occupied": occupied,
        "occupancy.flats.vacant": vacant,
        "occupancy.residents.count": residents,
        "billing.revenue.day": revenue_day,
        "billing.revenue.month": revenue_month,
        "billing.collected.month": revenue_month,
        "billing.billed.month": billed_month,
        "billing.outstanding.amount": outstanding,
        "billing.overdue.amount": overdue,
        "complaint.open.count": open_complaints,
        "complaint.resolved.month": resolved_month,
        "complaint.closed.month": closed_month,
        "visitor.checkins.day": visitor_day,
        "parking.slots.total": parking_total,
        "parking.slots.allocated": parking_alloc,
        "amenity.bookings.day": bookings_day,
        "notification.unread.count": unread_notif,
        "document.published.count": docs_pub,
        "notice.published.count": notices_pub,
        "notice.reads.count": notice_reads,
        "notice.targets.count": max(notices_pub, 1),
        "staff.on_duty.count": on_duty,
    }
    for key, val in metrics.items():
        await _upsert_daily(db, society_id, grain_date, key, val)
    await db.flush()
    return metrics


async def rollup_month(db: AsyncSession, society_id: UUID, year: int, month: int) -> None:
    society_id = require_society_id(society_id)
    days = monthrange(year, month)[1]
    keys = (
        await db.execute(
            select(AnalyticsDailyFact.metric_key, func.sum(AnalyticsDailyFact.metric_value))
            .where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.grain_date >= date(year, month, 1),
                AnalyticsDailyFact.grain_date <= date(year, month, days),
                AnalyticsDailyFact.building_id.is_(None),
            )
            .group_by(AnalyticsDailyFact.metric_key)
        )
    ).all()
    for metric_key, total in keys:
        existing = (
            await db.execute(
                select(AnalyticsMonthlyFact).where(
                    AnalyticsMonthlyFact.society_id == society_id,
                    AnalyticsMonthlyFact.year == year,
                    AnalyticsMonthlyFact.month == month,
                    AnalyticsMonthlyFact.metric_key == metric_key,
                    AnalyticsMonthlyFact.building_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        # For snapshot-style metrics use last day value preference for rates/amounts
        last = (
            await db.execute(
                select(AnalyticsDailyFact.metric_value)
                .where(
                    AnalyticsDailyFact.society_id == society_id,
                    AnalyticsDailyFact.metric_key == metric_key,
                    AnalyticsDailyFact.grain_date <= date(year, month, days),
                    AnalyticsDailyFact.building_id.is_(None),
                )
                .order_by(AnalyticsDailyFact.grain_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        value = int(last if metric_key.endswith((".amount", ".count", ".total", ".allocated", ".occupied", ".vacant")) and "day" not in metric_key and "month" not in metric_key else (total or 0))
        if "revenue" in metric_key or "collected" in metric_key or metric_key.endswith(".day"):
            value = int(total or 0)
        if existing:
            existing.metric_value = value
        else:
            db.add(
                AnalyticsMonthlyFact(
                    society_id=society_id,
                    year=year,
                    month=month,
                    metric_key=metric_key,
                    metric_value=value,
                )
            )
    await db.flush()


async def rebuild_range(
    db: AsyncSession, society_id: UUID, from_date: date | None = None, to_date: date | None = None
) -> dict:
    society_id = require_society_id(society_id)
    to_date = to_date or date.today()
    from_date = from_date or (to_date - timedelta(days=30))
    cur = from_date
    days = 0
    while cur <= to_date:
        await rebuild_society_day(db, society_id, cur)
        days += 1
        cur += timedelta(days=1)
    # monthly rollups
    y, m = from_date.year, from_date.month
    while (y, m) <= (to_date.year, to_date.month):
        await rollup_month(db, society_id, y, m)
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    await refresh_kpi_snapshots(db, society_id)
    return {"days": days, "from": from_date.isoformat(), "to": to_date.isoformat()}


async def increment_metric(
    db: AsyncSession,
    society_id: UUID,
    metric_key: str,
    delta: int = 1,
    grain_date: date | None = None,
) -> None:
    society_id = require_society_id(society_id)
    grain_date = grain_date or date.today()
    row = (
        await db.execute(
            select(AnalyticsDailyFact).where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.grain_date == grain_date,
                AnalyticsDailyFact.metric_key == metric_key,
                AnalyticsDailyFact.building_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row:
        row.metric_value = int(row.metric_value or 0) + int(delta)
    else:
        db.add(
            AnalyticsDailyFact(
                society_id=society_id,
                grain_date=grain_date,
                metric_key=metric_key,
                metric_value=int(delta),
            )
        )
    await db.flush()


async def _metric_value(db: AsyncSession, society_id: UUID, metric_key: str) -> int:
    # prefer today fact, else live rebuild snippet via latest fact
    today = date.today()
    val = (
        await db.execute(
            select(AnalyticsDailyFact.metric_value).where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.metric_key == metric_key,
                AnalyticsDailyFact.grain_date == today,
                AnalyticsDailyFact.building_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if val is not None:
        return int(val)
    latest = (
        await db.execute(
            select(AnalyticsDailyFact.metric_value)
            .where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.metric_key == metric_key,
                AnalyticsDailyFact.building_id.is_(None),
            )
            .order_by(AnalyticsDailyFact.grain_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return int(latest or 0)


async def compute_live_kpi(
    db: AsyncSession, society_id: UUID, definition: AnalyticsKpiDefinition
) -> dict:
    unit = definition.unit
    if definition.formula_type == "ratio":
        num = await _metric_value(db, society_id, definition.numerator_key or "")
        den = await _metric_value(db, society_id, definition.denominator_key or "")
        value = int(round((num / den) * 100)) if den else 0
        return {
            "kpiKey": definition.kpi_key,
            "name": definition.name,
            "unit": unit,
            "value": value,
            "numerator": num,
            "denominator": den,
        }
    metric = definition.metric_key or definition.kpi_key
    value = await _metric_value(db, society_id, metric)
    return {
        "kpiKey": definition.kpi_key,
        "name": definition.name,
        "unit": unit,
        "value": value,
    }


async def refresh_kpi_snapshots(db: AsyncSession, society_id: UUID, actor_id: UUID | None = None) -> dict:
    society_id = require_society_id(society_id)
    await ensure_catalog_seeded(db, society_id)
    await rebuild_society_day(db, society_id, date.today())
    defs = (
        await db.execute(
            select(AnalyticsKpiDefinition).where(
                AnalyticsKpiDefinition.society_id == society_id,
                AnalyticsKpiDefinition.is_active.is_(True),
            )
        )
    ).scalars().all()
    as_of = datetime.now(timezone.utc)
    results = []
    for d in defs:
        if d.kpi_key == "my_outstanding":
            continue
        payload = await compute_live_kpi(db, society_id, d)
        db.add(
            AnalyticsKpiSnapshot(
                society_id=society_id,
                kpi_key=d.kpi_key,
                as_of=as_of,
                value=int(payload.get("value") or 0),
                numerator=payload.get("numerator"),
                denominator=payload.get("denominator"),
                payload_json=payload,
            )
        )
        results.append(payload)
    await db.flush()
    publish_simple(
        "AnalyticsSnapshotRefreshed",
        society_id=society_id,
        entity_type="analytics_kpi_snapshot",
        entity_id=None,
        actor_id=actor_id,
        payload={"count": len(results)},
    )
    return {"asOf": iso(as_of), "kpis": results}


async def list_kpi_definitions(db: AsyncSession, society_id: UUID, role: str) -> list:
    await ensure_catalog_seeded(db, society_id)
    rows = (
        await db.execute(
            select(AnalyticsKpiDefinition)
            .where(
                AnalyticsKpiDefinition.society_id == society_id,
                AnalyticsKpiDefinition.is_active.is_(True),
            )
            .order_by(AnalyticsKpiDefinition.sort_order)
        )
    ).scalars().all()
    return [serialize_kpi_def(r) for r in rows if role_allowed(r.roles_json, role)]


async def get_kpis(
    db: AsyncSession,
    society_id: UUID,
    role: str,
    keys: list[str] | None = None,
    *,
    live: bool = True,
) -> list:
    await ensure_catalog_seeded(db, society_id)
    stmt = select(AnalyticsKpiDefinition).where(
        AnalyticsKpiDefinition.society_id == society_id,
        AnalyticsKpiDefinition.is_active.is_(True),
    )
    if keys:
        stmt = stmt.where(AnalyticsKpiDefinition.kpi_key.in_(keys))
    defs = (await db.execute(stmt.order_by(AnalyticsKpiDefinition.sort_order))).scalars().all()
    out = []
    for d in defs:
        if not role_allowed(d.roles_json, role):
            continue
        if live:
            out.append(await compute_live_kpi(db, society_id, d))
        else:
            snap = (
                await db.execute(
                    select(AnalyticsKpiSnapshot)
                    .where(
                        AnalyticsKpiSnapshot.society_id == society_id,
                        AnalyticsKpiSnapshot.kpi_key == d.kpi_key,
                    )
                    .order_by(AnalyticsKpiSnapshot.as_of.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if snap:
                out.append(snap.payload_json or {"kpiKey": d.kpi_key, "value": snap.value, "name": d.name, "unit": d.unit})
            else:
                out.append(await compute_live_kpi(db, society_id, d))
    return out


async def list_reports(db: AsyncSession, society_id: UUID, role: str, category: str | None = None, search: str | None = None) -> list:
    await ensure_catalog_seeded(db, society_id)
    stmt = select(AnalyticsReportDefinition).where(
        AnalyticsReportDefinition.society_id == society_id,
        AnalyticsReportDefinition.is_active.is_(True),
    )
    if category:
        stmt = stmt.where(AnalyticsReportDefinition.category == category)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                AnalyticsReportDefinition.name.ilike(like),
                AnalyticsReportDefinition.report_key.ilike(like),
            )
        )
    rows = (await db.execute(stmt.order_by(AnalyticsReportDefinition.sort_order))).scalars().all()
    return [serialize_report_def(r) for r in rows if role_allowed(r.roles_json, role)]


async def _fact_series(db: AsyncSession, society_id: UUID, metric_key: str, days: int = 14) -> list:
    start = date.today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(AnalyticsDailyFact)
            .where(
                AnalyticsDailyFact.society_id == society_id,
                AnalyticsDailyFact.metric_key == metric_key,
                AnalyticsDailyFact.grain_date >= start,
                AnalyticsDailyFact.building_id.is_(None),
            )
            .order_by(AnalyticsDailyFact.grain_date)
        )
    ).scalars().all()
    return [{"label": r.grain_date.isoformat()[5:], "value": int(r.metric_value)} for r in rows]


async def execute_report(
    db: AsyncSession,
    society_id: UUID,
    role: str,
    report_key: str,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: UUID | None = None,
    resident_id: UUID | None = None,
) -> dict:
    await ensure_catalog_seeded(db, society_id)
    definition = (
        await db.execute(
            select(AnalyticsReportDefinition).where(
                AnalyticsReportDefinition.society_id == society_id,
                AnalyticsReportDefinition.report_key == report_key,
                AnalyticsReportDefinition.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not definition or not role_allowed(definition.roles_json, role):
        raise ApiError(404, "Report not found")

    await log_access(
        db,
        society_id=society_id,
        user_id=user_id,
        action="report_view",
        resource_type="report",
        resource_key=report_key,
    )

    rows: list[dict] = []
    columns = [
        {"key": "label", "label": "Label"},
        {"key": "value", "label": "Value"},
    ]

    if report_key.startswith("resident.") and role == "resident":
        if report_key == "resident.billing":
            stmt = select(MaintenanceBill).where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.is_active.is_(True),
            )
            if resident_id:
                stmt = stmt.where(MaintenanceBill.resident_id == resident_id)
            q = (
                await db.execute(
                    stmt.order_by(MaintenanceBill.created_at.desc()).limit(page_size)
                )
            ).scalars().all()
            columns = [
                {"key": "billNumber", "label": "Bill"},
                {"key": "status", "label": "Status"},
                {"key": "outstandingMinor", "label": "Outstanding"},
            ]
            rows = [
                {
                    "billNumber": b.bill_number,
                    "status": b.status,
                    "outstandingMinor": b.outstanding_minor,
                }
                for b in q
            ]
        else:
            rows = [{"label": report_key, "value": "See module pages for detail"}]
    elif report_key in ("billing.outstanding", "finance.revenue", "billing.collections"):
        await rebuild_society_day(db, society_id)
        metrics = [
            ("Outstanding", await _metric_value(db, society_id, "billing.outstanding.amount")),
            ("Overdue", await _metric_value(db, society_id, "billing.overdue.amount")),
            ("Month collections", await _metric_value(db, society_id, "billing.revenue.month")),
            ("Today collections", await _metric_value(db, society_id, "billing.revenue.day")),
        ]
        rows = [{"label": a, "value": b} for a, b in metrics]
    elif report_key == "visitors.daily":
        series = await _fact_series(db, society_id, "visitor.checkins.day")
        if not series:
            await rebuild_society_day(db, society_id)
            series = await _fact_series(db, society_id, "visitor.checkins.day")
        rows = series
    elif report_key == "complaints.pipeline":
        statuses = ("open", "in_progress", "pending", "resolved", "closed")
        for st in statuses:
            cnt = int(
                (
                    await db.execute(
                        select(func.count(Complaint.id)).where(
                            Complaint.society_id == society_id,
                            Complaint.status == st,
                        )
                    )
                ).scalar_one()
                or 0
            )
            rows.append({"label": st, "value": cnt})
    elif report_key == "parking.occupancy":
        rows = [
            {"label": "Total slots", "value": await _metric_value(db, society_id, "parking.slots.total")},
            {"label": "Allocated", "value": await _metric_value(db, society_id, "parking.slots.allocated")},
        ]
    elif report_key == "society.occupancy":
        rows = [
            {"label": "Occupied", "value": await _metric_value(db, society_id, "occupancy.flats.occupied")},
            {"label": "Vacant", "value": await _metric_value(db, society_id, "occupancy.flats.vacant")},
            {"label": "Residents", "value": await _metric_value(db, society_id, "occupancy.residents.count")},
        ]
    elif report_key == "operational.today":
        rows = [
            {"label": "Visitors today", "value": await _metric_value(db, society_id, "visitor.checkins.day")},
            {"label": "Bookings today", "value": await _metric_value(db, society_id, "amenity.bookings.day")},
            {"label": "Staff on duty", "value": await _metric_value(db, society_id, "staff.on_duty.count")},
        ]
        if role != "guard":
            rows.insert(
                2,
                {
                    "label": "Open complaints",
                    "value": await _metric_value(db, society_id, "complaint.open.count"),
                },
            )
    elif report_key == "audit.access":
        logs = (
            await db.execute(
                select(AnalyticsAccessLog)
                .where(AnalyticsAccessLog.society_id == society_id)
                .order_by(AnalyticsAccessLog.created_at.desc())
                .limit(page_size)
            )
        ).scalars().all()
        columns = [
            {"key": "action", "label": "Action"},
            {"key": "resourceKey", "label": "Key"},
            {"key": "createdAt", "label": "When"},
        ]
        rows = [
            {"action": l.action, "resourceKey": l.resource_key, "createdAt": iso(l.created_at)}
            for l in logs
        ]
    else:
        # generic executive / catalog fallback from today's metrics
        await rebuild_society_day(db, society_id)
        facts = (
            await db.execute(
                select(AnalyticsDailyFact).where(
                    AnalyticsDailyFact.society_id == society_id,
                    AnalyticsDailyFact.grain_date == date.today(),
                    AnalyticsDailyFact.building_id.is_(None),
                )
            )
        ).scalars().all()
        rows = [{"label": f.metric_key, "value": int(f.metric_value)} for f in facts]

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    return {
        "report": serialize_report_def(definition),
        "columns": columns,
        "rows": page_rows,
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def chart_series(
    db: AsyncSession, society_id: UUID, role: str, chart_key: str, chart_type: str = "bar"
) -> dict:
    # reuse report execution for table then map
    data = await execute_report(db, society_id, role, chart_key, page=1, page_size=50)
    series = []
    for r in data.get("rows") or []:
        if "label" in r and "value" in r:
            series.append({"label": str(r["label"]), "value": r["value"]})
        else:
            # first two values
            vals = list(r.values())
            if len(vals) >= 2:
                series.append({"label": str(vals[0]), "value": vals[1]})
    # prefer time series for collections
    if chart_key in ("billing.collections", "finance.revenue"):
        series = await _fact_series(db, society_id, "billing.revenue.day", days=14)
        if not series:
            await rebuild_society_day(db, society_id)
            series = await _fact_series(db, society_id, "billing.revenue.day", days=14)
        chart_type = "line"
    return {
        "chartKey": chart_key,
        "type": chart_type,
        "name": data.get("report", {}).get("name", chart_key),
        "series": series,
    }


async def get_dashboard(
    db: AsyncSession,
    society_id: UUID,
    role: str,
    layout_key: str | None = None,
    *,
    user_id: UUID | None = None,
    resident_id: UUID | None = None,
) -> dict:
    await ensure_catalog_seeded(db, society_id)
    await rebuild_society_day(db, society_id)
    key = layout_key or (
        "executive" if role == "admin" else "finance" if role == "finance" else "today" if role == "guard" else "summary"
    )
    layout = (
        await db.execute(
            select(AnalyticsDashboardLayout).where(
                AnalyticsDashboardLayout.society_id == society_id,
                AnalyticsDashboardLayout.role == role,
                AnalyticsDashboardLayout.layout_key == key,
                AnalyticsDashboardLayout.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    widgets = layout.widgets_json if layout else []
    kpi_keys = [w["kpiKey"] for w in widgets if w.get("type") == "kpi_card" and w.get("kpiKey")]
    kpis = await get_kpis(db, society_id, role, kpi_keys or None)
    if role == "resident" and resident_id:
        outstanding = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(MaintenanceBill.outstanding_minor), 0)).where(
                        MaintenanceBill.society_id == society_id,
                        MaintenanceBill.resident_id == resident_id,
                        MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
                        MaintenanceBill.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
        kpis = [
            {"kpiKey": "my_outstanding", "name": "My Outstanding", "unit": "minor_currency", "value": outstanding}
        ] + [k for k in kpis if k.get("kpiKey") != "my_outstanding"]

    charts = []
    for w in widgets:
        if w.get("type") == "chart" and w.get("chartKey"):
            try:
                charts.append(
                    await chart_series(
                        db, society_id, role, w["chartKey"], w.get("chartType") or "bar"
                    )
                )
            except ApiError:
                continue

    await log_access(
        db,
        society_id=society_id,
        user_id=user_id,
        action="dashboard_view",
        resource_type="dashboard",
        resource_key=key,
    )
    return {
        "layoutKey": key,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "sourceFreshness": "live",
        "kpis": kpis,
        "charts": charts,
        "sections": [
            {"key": "resident.billing", "label": "My billing summary"},
            {"key": "resident.visitors", "label": "My visitor history"},
            {"key": "resident.parking", "label": "My parking"},
            {"key": "resident.amenities", "label": "My amenity bookings"},
        ]
        if role == "resident"
        else [],
    }


async def create_export(
    db: AsyncSession,
    society_id: UUID,
    role: str,
    *,
    report_key: str,
    format: str = "csv",
    filters: dict | None = None,
    user_id: UUID | None = None,
    resident_id: UUID | None = None,
) -> dict:
    society_id = require_society_id(society_id)
    fmt = (format or "csv").lower()
    if fmt not in ("csv", "excel", "pdf"):
        raise ApiError(422, "Invalid export format")
    if role == "guard" and report_key not in ("operational.today", "visitors.daily", "parking.occupancy", "security.ops"):
        raise ApiError(403, "Guard cannot export this report")
    if role == "finance" and not report_key.startswith(("billing.", "finance.", "documents.", "amenities.", "parking.", "notifications.")):
        # allow finance category keys
        defn = (
            await db.execute(
                select(AnalyticsReportDefinition).where(
                    AnalyticsReportDefinition.society_id == society_id,
                    AnalyticsReportDefinition.report_key == report_key,
                )
            )
        ).scalar_one_or_none()
        if not defn or not role_allowed(defn.roles_json, role):
            raise ApiError(403, "Finance cannot export this report")
    if role == "resident" and not report_key.startswith("resident."):
        raise ApiError(403, "Residents can only export personal reports")

    publish_simple(
        "ReportExportQueued",
        society_id=society_id,
        entity_type="analytics_export_job",
        actor_id=user_id,
        payload={"reportKey": report_key, "format": fmt},
    )
    try:
        data = await execute_report(
            db,
            society_id,
            role,
            report_key,
            page=1,
            page_size=5000,
            user_id=user_id,
            resident_id=resident_id,
        )
        rows = data.get("rows") or []
        columns = data.get("columns") or []
        keys = [c["key"] for c in columns] or (list(rows[0].keys()) if rows else ["label", "value"])
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in keys})
        content = buf.getvalue()
        if fmt == "pdf":
            content = "PDF export (text)\n\n" + content
        elif fmt == "excel":
            content = "Excel-compatible CSV\n" + content
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        job = AnalyticsExportJob(
            society_id=society_id,
            report_key=report_key,
            format=fmt,
            status="completed",
            filters_json=filters or {},
            file_name=f"{report_key.replace('.', '_')}.{ 'csv' if fmt != 'pdf' else 'txt'}",
            content_text=content,
            row_count=len(rows),
            byte_size=len(content.encode("utf-8")),
            requested_by=user_id,
            created_by=user_id,
            expires_at=expires,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.flush()
        publish_simple(
            "ReportExportCompleted",
            society_id=society_id,
            entity_type="analytics_export_job",
            entity_id=job.id,
            actor_id=user_id,
            payload={"reportKey": report_key, "rowCount": len(rows)},
        )
        await log_access(
            db,
            society_id=society_id,
            user_id=user_id,
            action="export_create",
            resource_type="export",
            resource_key=report_key,
        )
        return serialize_export(job)
    except Exception as exc:
        publish_simple(
            "ReportExportFailed",
            society_id=society_id,
            entity_type="analytics_export_job",
            actor_id=user_id,
            payload={"reportKey": report_key, "error": str(exc)},
        )
        raise


def serialize_export(job: AnalyticsExportJob) -> dict:
    return {
        "id": str(job.id),
        "reportKey": job.report_key,
        "format": job.format,
        "status": job.status,
        "fileName": job.file_name,
        "rowCount": job.row_count,
        "byteSize": job.byte_size,
        "expiresAt": iso(job.expires_at),
        "completedAt": iso(job.completed_at),
        "createdAt": iso(job.created_at),
        "errorMessage": job.error_message,
    }


async def list_exports(db: AsyncSession, society_id: UUID, user_id: UUID | None, role: str, page=1, page_size=10) -> dict:
    stmt = select(AnalyticsExportJob).where(
        AnalyticsExportJob.society_id == society_id,
        AnalyticsExportJob.is_active.is_(True),
    )
    if role != "admin":
        stmt = stmt.where(AnalyticsExportJob.requested_by == user_id)
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0
    )
    rows = (
        await db.execute(
            stmt.order_by(AnalyticsExportJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "exports": [serialize_export(r) for r in rows],
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def get_export(db: AsyncSession, society_id: UUID, export_id: UUID, user_id: UUID | None, role: str) -> AnalyticsExportJob:
    job = (
        await db.execute(
            select(AnalyticsExportJob).where(
                AnalyticsExportJob.id == export_id,
                AnalyticsExportJob.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise ApiError(404, "Export not found")
    if role != "admin" and job.requested_by != user_id:
        raise ApiError(404, "Export not found")
    if job.expires_at and job.expires_at < datetime.now(timezone.utc):
        job.status = "expired"
        raise ApiError(400, "Export expired")
    return job


async def download_export(
    db: AsyncSession, society_id: UUID, export_id: UUID, user_id: UUID | None, role: str
) -> tuple[AnalyticsExportJob, str]:
    job = await get_export(db, society_id, export_id, user_id, role)
    db.add(
        AnalyticsExportDownload(
            society_id=society_id, export_job_id=job.id, user_id=user_id
        )
    )
    await log_access(
        db,
        society_id=society_id,
        user_id=user_id,
        action="export_download",
        resource_type="export",
        resource_key=str(job.id),
    )
    await db.flush()
    return job, job.content_text or ""


def _next_run(frequency: str, from_dt: datetime | None = None) -> datetime:
    now = from_dt or datetime.now(timezone.utc)
    if frequency == "daily":
        return now + timedelta(days=1)
    if frequency == "weekly":
        return now + timedelta(days=7)
    if frequency == "monthly":
        return now + timedelta(days=30)
    if frequency == "quarterly":
        return now + timedelta(days=90)
    if frequency == "yearly":
        return now + timedelta(days=365)
    return now + timedelta(days=1)


def serialize_schedule(s: ReportSchedule) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "reportKey": s.report_key,
        "format": s.format,
        "frequency": s.frequency,
        "cronExpression": s.cron_expression,
        "nextRunAt": iso(s.next_run_at),
        "lastRunAt": iso(s.last_run_at),
        "isActive": s.is_active,
        "createdAt": iso(s.created_at),
    }


async def create_schedule(db: AsyncSession, society_id: UUID, user_id: UUID | None, payload: dict, role: str) -> dict:
    if role not in ("admin", "finance"):
        raise ApiError(403, "Not allowed to create schedules")
    freq = payload.get("frequency") or "monthly"
    sched = ReportSchedule(
        society_id=society_id,
        name=payload["name"],
        report_key=payload["reportKey"],
        format=payload.get("format") or "csv",
        frequency=freq,
        cron_expression=payload.get("cronExpression"),
        filters_json=payload.get("filters") or {},
        recipient_user_ids_json=payload.get("recipientUserIds") or [],
        recipient_roles_json=payload.get("recipientRoles") or ([role] if role else []),
        next_run_at=_next_run(freq),
        created_by=user_id,
    )
    db.add(sched)
    await db.flush()
    return serialize_schedule(sched)


async def list_schedules(db: AsyncSession, society_id: UUID, role: str, page=1, page_size=10) -> dict:
    stmt = select(ReportSchedule).where(
        ReportSchedule.society_id == society_id,
        ReportSchedule.is_active.is_(True),
    )
    if role == "finance":
        stmt = stmt.where(
            or_(
                ReportSchedule.created_by.is_not(None),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(
            stmt.order_by(ReportSchedule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    if role == "finance":
        rows = [r for r in rows if "finance" in (r.recipient_roles_json or []) or r.report_key.startswith(("billing.", "finance."))]
    return {
        "schedules": [serialize_schedule(r) for r in rows],
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def update_schedule(db: AsyncSession, society_id: UUID, schedule_id: UUID, payload: dict) -> dict:
    sched = (
        await db.execute(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id, ReportSchedule.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if not sched:
        raise ApiError(404, "Schedule not found")
    for field, attr in (
        ("name", "name"),
        ("reportKey", "report_key"),
        ("format", "format"),
        ("frequency", "frequency"),
        ("cronExpression", "cron_expression"),
    ):
        if field in payload and payload[field] is not None:
            setattr(sched, attr, payload[field])
    if "filters" in payload:
        sched.filters_json = payload["filters"] or {}
    if "isActive" in payload:
        sched.is_active = bool(payload["isActive"])
    if "frequency" in payload:
        sched.next_run_at = _next_run(sched.frequency)
    await db.flush()
    return serialize_schedule(sched)


async def soft_delete_schedule(db: AsyncSession, society_id: UUID, schedule_id: UUID) -> None:
    sched = (
        await db.execute(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id, ReportSchedule.society_id == society_id
            )
        )
    ).scalar_one_or_none()
    if not sched:
        raise ApiError(404, "Schedule not found")
    sched.is_active = False
    await db.flush()


async def list_schedule_runs(db: AsyncSession, society_id: UUID, schedule_id: UUID) -> list:
    rows = (
        await db.execute(
            select(ReportScheduleRun)
            .where(
                ReportScheduleRun.society_id == society_id,
                ReportScheduleRun.schedule_id == schedule_id,
            )
            .order_by(ReportScheduleRun.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "attempt": r.attempt,
            "errorMessage": r.error_message,
            "startedAt": iso(r.started_at),
            "completedAt": iso(r.completed_at),
        }
        for r in rows
    ]


async def run_due_schedules(db: AsyncSession, society_id: UUID | None = None) -> int:
    now = datetime.now(timezone.utc)
    stmt = select(ReportSchedule).where(
        ReportSchedule.is_active.is_(True),
        ReportSchedule.next_run_at <= now,
    )
    if society_id:
        stmt = stmt.where(ReportSchedule.society_id == society_id)
    schedules = (await db.execute(stmt)).scalars().all()
    ran = 0
    for sched in schedules:
        run = ReportScheduleRun(
            society_id=sched.society_id,
            schedule_id=sched.id,
            status="pending",
            started_at=now,
        )
        db.add(run)
        await db.flush()
        try:
            role = (sched.recipient_roles_json or ["admin"])[0]
            job = await create_export(
                db,
                sched.society_id,
                role if role in ("admin", "finance", "guard", "resident") else "admin",
                report_key=sched.report_key,
                format=sched.format,
                filters=sched.filters_json,
                user_id=sched.created_by,
            )
            run.status = "completed"
            run.export_job_id = UUID(job["id"])
            run.completed_at = datetime.now(timezone.utc)
            sched.last_run_at = run.completed_at
            sched.next_run_at = _next_run(sched.frequency, run.completed_at)
            publish_simple(
                "ReportScheduleRunCompleted",
                society_id=sched.society_id,
                entity_type="report_schedule_run",
                entity_id=run.id,
                actor_id=sched.created_by,
                payload={"scheduleId": str(sched.id), "exportId": job["id"]},
            )
            ran += 1
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            sched.next_run_at = _next_run(sched.frequency)
    await db.flush()
    return ran


async def get_preferences(db: AsyncSession, society_id: UUID, user_id: UUID) -> dict:
    row = (
        await db.execute(
            select(AnalyticsUserPreference).where(
                AnalyticsUserPreference.society_id == society_id,
                AnalyticsUserPreference.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return {"favoriteReportKeys": [], "defaultFilters": {}, "savedFilters": []}
    return {
        "favoriteReportKeys": row.favorite_report_keys_json or [],
        "defaultFilters": row.default_filters_json or {},
        "savedFilters": row.saved_filters_json or [],
    }


async def patch_preferences(db: AsyncSession, society_id: UUID, user_id: UUID, payload: dict) -> dict:
    row = (
        await db.execute(
            select(AnalyticsUserPreference).where(
                AnalyticsUserPreference.society_id == society_id,
                AnalyticsUserPreference.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        row = AnalyticsUserPreference(society_id=society_id, user_id=user_id)
        db.add(row)
    if "favoriteReportKeys" in payload:
        row.favorite_report_keys_json = payload["favoriteReportKeys"] or []
    if "defaultFilters" in payload:
        row.default_filters_json = payload["defaultFilters"] or {}
    if "savedFilters" in payload:
        row.saved_filters_json = payload["savedFilters"] or []
    await db.flush()
    return await get_preferences(db, society_id, user_id)


async def list_access_logs(db: AsyncSession, society_id: UUID, page=1, page_size=20) -> dict:
    stmt = select(AnalyticsAccessLog).where(AnalyticsAccessLog.society_id == society_id)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one() or 0)
    rows = (
        await db.execute(
            stmt.order_by(AnalyticsAccessLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "logs": [
            {
                "id": str(r.id),
                "action": r.action,
                "resourceType": r.resource_type,
                "resourceKey": r.resource_key,
                "createdAt": iso(r.created_at),
            }
            for r in rows
        ],
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def get_catalog(db: AsyncSession, society_id: UUID, role: str) -> dict:
    await ensure_catalog_seeded(db, society_id)
    return {
        "kpis": await list_kpi_definitions(db, society_id, role),
        "reports": await list_reports(db, society_id, role),
        "categories": sorted({r["category"] for r in await list_reports(db, society_id, role)}),
    }
