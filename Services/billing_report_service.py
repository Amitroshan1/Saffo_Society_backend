"""Billing report payloads."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.charge_head import ChargeHead
from Models.flat import Flat
from Models.maintenance_bill import BillLineItem, MaintenanceBill
from Models.payment import Payment, PaymentAllocation
from Models.resident import Resident
from Services.billing_helpers import require_society_id
from Utils.errors import ApiError

REPORT_KEYS = {
    "outstanding",
    "collections",
    "revenue",
    "defaulters",
    "resident_ledger",
    "income",
    "charge_head_summary",
    "monthly_collections",
    "yearly_collections",
    "payment_trends",
}


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label} date") from exc


def _parse_uuid(value: Optional[str], label: str) -> Optional[UUID]:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label}") from exc


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
        "outstanding": _outstanding,
        "collections": _collections,
        "revenue": _revenue,
        "defaulters": _defaulters,
        "resident_ledger": _resident_ledger,
        "income": _income,
        "charge_head_summary": _charge_head_summary,
        "monthly_collections": _monthly_collections,
        "yearly_collections": _yearly_collections,
        "payment_trends": _payment_trends,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


async def _outstanding(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    as_of = _parse_date(filters.get("asOf"), "asOf") or date.today()
    building_id = _parse_uuid(filters.get("buildingId"), "buildingId")
    wing_id = _parse_uuid(filters.get("wingId"), "wingId")
    stmt = select(MaintenanceBill).where(
        MaintenanceBill.society_id == society_id,
        MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
        MaintenanceBill.outstanding_minor > 0,
        MaintenanceBill.bill_date <= as_of,
        MaintenanceBill.is_active.is_(True),
    )
    if building_id:
        stmt = stmt.where(MaintenanceBill.building_id == building_id)
    if wing_id:
        stmt = stmt.where(MaintenanceBill.wing_id == wing_id)
    bills = (await db.execute(stmt.order_by(MaintenanceBill.due_date.asc()))).scalars().all()
    residents = {
        r.id: r
        for r in (
            await db.execute(
                select(Resident).where(Resident.id.in_({b.resident_id for b in bills} or {UUID(int=0)}))
            )
        ).scalars().all()
    } if bills else {}
    flats = {
        f.id: f
        for f in (
            await db.execute(
                select(Flat).where(Flat.id.in_({b.flat_id for b in bills} or {UUID(int=0)}))
            )
        ).scalars().all()
    } if bills else {}
    return [
        {
            "billId": str(b.id),
            "billNumber": b.bill_number,
            "residentId": str(b.resident_id),
            "residentName": residents[b.resident_id].name if b.resident_id in residents else None,
            "flatNo": flats[b.flat_id].flat_no if b.flat_id in flats else None,
            "dueDate": b.due_date.isoformat(),
            "outstandingMinor": b.outstanding_minor,
            "status": b.status,
        }
        for b in bills
    ]


async def _collections(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    from_d = _parse_date(filters.get("from"), "from") or date.today().replace(day=1)
    to_d = _parse_date(filters.get("to"), "to") or date.today()
    mode = filters.get("mode")
    start = datetime.combine(from_d, time.min, tzinfo=timezone.utc)
    end = datetime.combine(to_d, time.max, tzinfo=timezone.utc)
    stmt = select(Payment).where(
        Payment.society_id == society_id,
        Payment.status == "cleared",
        Payment.payment_date >= start,
        Payment.payment_date <= end,
    )
    if mode:
        stmt = stmt.where(Payment.mode == mode.strip().lower())
    payments = (await db.execute(stmt.order_by(Payment.payment_date.asc()))).scalars().all()
    return [
        {
            "paymentId": str(p.id),
            "paymentNumber": p.payment_number,
            "paymentDate": p.payment_date.isoformat(),
            "mode": p.mode,
            "amountMinor": p.amount_minor,
            "residentId": str(p.resident_id),
        }
        for p in payments
    ]


async def _revenue(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    fy_id = _parse_uuid(filters.get("financialYearId") or filters.get("fy"), "financialYearId")
    period_id = _parse_uuid(filters.get("periodId") or filters.get("period"), "periodId")
    bill_stmt = select(
        func.coalesce(func.sum(MaintenanceBill.net_minor), 0),
        func.coalesce(func.sum(MaintenanceBill.paid_minor), 0),
    ).where(
        MaintenanceBill.society_id == society_id,
        MaintenanceBill.status.notin_(("cancelled", "draft")),
    )
    pay_stmt = select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
        Payment.society_id == society_id,
        Payment.status == "cleared",
    )
    if fy_id:
        bill_stmt = bill_stmt.where(MaintenanceBill.financial_year_id == fy_id)
        pay_stmt = pay_stmt.where(Payment.financial_year_id == fy_id)
    if period_id:
        bill_stmt = bill_stmt.where(MaintenanceBill.accounting_period_id == period_id)
        pay_stmt = pay_stmt.where(Payment.accounting_period_id == period_id)
    billed, paid = (await db.execute(bill_stmt)).one()
    collected = (await db.execute(pay_stmt)).scalar_one()
    return [
        {
            "billedMinor": int(billed or 0),
            "paidOnBillsMinor": int(paid or 0),
            "collectedMinor": int(collected or 0),
        }
    ]


async def _defaulters(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    min_outstanding = int(filters.get("minOutstanding") or 0)
    days_overdue = int(filters.get("daysOverdue") or 0)
    cutoff = date.today()
    rows = (
        await db.execute(
            select(
                MaintenanceBill.resident_id,
                MaintenanceBill.flat_id,
                func.sum(MaintenanceBill.outstanding_minor),
                func.min(MaintenanceBill.due_date),
            )
            .where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
                MaintenanceBill.outstanding_minor > 0,
                MaintenanceBill.is_active.is_(True),
            )
            .group_by(MaintenanceBill.resident_id, MaintenanceBill.flat_id)
            .having(func.sum(MaintenanceBill.outstanding_minor) >= min_outstanding)
            .order_by(func.sum(MaintenanceBill.outstanding_minor).desc())
        )
    ).all()
    result = []
    resident_ids = {r[0] for r in rows}
    flat_ids = {r[1] for r in rows}
    residents = {
        x.id: x
        for x in (
            await db.execute(select(Resident).where(Resident.id.in_(resident_ids or {UUID(int=0)})))
        ).scalars().all()
    } if resident_ids else {}
    flats = {
        x.id: x
        for x in (
            await db.execute(select(Flat).where(Flat.id.in_(flat_ids or {UUID(int=0)})))
        ).scalars().all()
    } if flat_ids else {}
    for rid, fid, amt, due in rows:
        overdue_days = (cutoff - due).days if due else 0
        if overdue_days < days_overdue:
            continue
        result.append(
            {
                "residentId": str(rid),
                "residentName": residents[rid].name if rid in residents else None,
                "flatNo": flats[fid].flat_no if fid in flats else None,
                "outstandingMinor": int(amt or 0),
                "oldestDueDate": due.isoformat() if due else None,
                "daysOverdue": overdue_days,
            }
        )
    return result


async def _resident_ledger(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    resident_id = _parse_uuid(filters.get("residentId"), "residentId")
    occupancy_id = _parse_uuid(filters.get("occupancyId"), "occupancyId")
    if not resident_id and not occupancy_id:
        raise ApiError(422, "residentId or occupancyId is required")
    entries: list[dict] = []
    bill_stmt = select(MaintenanceBill).where(
        MaintenanceBill.society_id == society_id,
        MaintenanceBill.is_active.is_(True),
    )
    pay_stmt = select(Payment).where(Payment.society_id == society_id)
    if resident_id:
        bill_stmt = bill_stmt.where(MaintenanceBill.resident_id == resident_id)
        pay_stmt = pay_stmt.where(Payment.resident_id == resident_id)
    if occupancy_id:
        bill_stmt = bill_stmt.where(MaintenanceBill.occupancy_id == occupancy_id)
        pay_stmt = pay_stmt.where(Payment.occupancy_id == occupancy_id)
    for b in (await db.execute(bill_stmt)).scalars().all():
        entries.append(
            {
                "type": "bill",
                "date": b.bill_date.isoformat(),
                "reference": b.bill_number,
                "debitMinor": b.net_minor,
                "creditMinor": 0,
                "status": b.status,
            }
        )
    for p in (await db.execute(pay_stmt)).scalars().all():
        entries.append(
            {
                "type": "payment",
                "date": p.payment_date.date().isoformat(),
                "reference": p.payment_number,
                "debitMinor": 0,
                "creditMinor": p.amount_minor if p.status == "cleared" else 0,
                "status": p.status,
            }
        )
    entries.sort(key=lambda e: e["date"])
    return entries


async def _income(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    fy_id = _parse_uuid(filters.get("financialYearId") or filters.get("fy"), "financialYearId")
    stmt = (
        select(
            BillLineItem.charge_head_id,
            func.coalesce(func.sum(PaymentAllocation.amount_minor), 0),
        )
        .select_from(PaymentAllocation)
        .join(MaintenanceBill, MaintenanceBill.id == PaymentAllocation.bill_id)
        .join(BillLineItem, BillLineItem.bill_id == MaintenanceBill.id)
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.society_id == society_id,
            PaymentAllocation.allocation_type == "bill",
            Payment.status == "cleared",
            BillLineItem.is_active.is_(True),
            BillLineItem.is_discount.is_(False),
        )
        .group_by(BillLineItem.charge_head_id)
    )
    if fy_id:
        stmt = stmt.where(Payment.financial_year_id == fy_id)
    rows = (await db.execute(stmt)).all()
    heads = {
        h.id: h
        for h in (
            await db.execute(
                select(ChargeHead).where(ChargeHead.id.in_({r[0] for r in rows} or {UUID(int=0)}))
            )
        ).scalars().all()
    } if rows else {}
    return [
        {
            "chargeHeadId": str(hid),
            "chargeHeadCode": heads[hid].code if hid in heads else None,
            "chargeHeadName": heads[hid].name if hid in heads else None,
            "collectedMinor": int(amt or 0),
        }
        for hid, amt in rows
    ]


async def _charge_head_summary(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = (
        select(
            BillLineItem.charge_head_id,
            func.coalesce(func.sum(BillLineItem.line_total_minor), 0),
        )
        .join(MaintenanceBill, MaintenanceBill.id == BillLineItem.bill_id)
        .where(
            BillLineItem.society_id == society_id,
            BillLineItem.is_active.is_(True),
            MaintenanceBill.status.notin_(("cancelled", "draft")),
        )
        .group_by(BillLineItem.charge_head_id)
    )
    if from_d:
        stmt = stmt.where(MaintenanceBill.bill_date >= from_d)
    if to_d:
        stmt = stmt.where(MaintenanceBill.bill_date <= to_d)
    rows = (await db.execute(stmt)).all()
    heads = {
        h.id: h
        for h in (
            await db.execute(
                select(ChargeHead).where(ChargeHead.id.in_({r[0] for r in rows} or {UUID(int=0)}))
            )
        ).scalars().all()
    } if rows else {}
    return [
        {
            "chargeHeadId": str(hid),
            "chargeHeadCode": heads[hid].code if hid in heads else None,
            "chargeHeadName": heads[hid].name if hid in heads else None,
            "billedMinor": int(amt or 0),
        }
        for hid, amt in rows
    ]


async def _monthly_collections(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    year = int(filters.get("year") or date.today().year)
    rows = (
        await db.execute(
            select(
                extract("month", Payment.payment_date).label("month"),
                func.coalesce(func.sum(Payment.amount_minor), 0),
            )
            .where(
                Payment.society_id == society_id,
                Payment.status == "cleared",
                extract("year", Payment.payment_date) == year,
            )
            .group_by(extract("month", Payment.payment_date))
            .order_by(extract("month", Payment.payment_date))
        )
    ).all()
    by_month = {int(m): int(amt or 0) for m, amt in rows}
    return [{"month": m, "amountMinor": by_month.get(m, 0)} for m in range(1, 13)]


async def _yearly_collections(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> list[dict]:
    rows = (
        await db.execute(
            select(
                extract("year", Payment.payment_date).label("year"),
                func.coalesce(func.sum(Payment.amount_minor), 0),
            )
            .where(Payment.society_id == society_id, Payment.status == "cleared")
            .group_by(extract("year", Payment.payment_date))
            .order_by(extract("year", Payment.payment_date))
        )
    ).all()
    return [{"year": int(y), "amountMinor": int(amt or 0)} for y, amt in rows]


async def _payment_trends(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> list[dict]:
    granularity = (filters.get("granularity") or "month").strip().lower()
    if granularity not in {"week", "month"}:
        raise ApiError(422, "granularity must be week or month")
    part = extract("week", Payment.payment_date) if granularity == "week" else extract(
        "month", Payment.payment_date
    )
    year_part = extract("year", Payment.payment_date)
    rows = (
        await db.execute(
            select(
                year_part.label("year"),
                part.label("bucket"),
                Payment.mode,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount_minor), 0),
            )
            .where(Payment.society_id == society_id, Payment.status == "cleared")
            .group_by(year_part, part, Payment.mode)
            .order_by(year_part, part)
        )
    ).all()
    return [
        {
            "year": int(y),
            "bucket": int(b),
            "mode": mode,
            "count": int(cnt or 0),
            "amountMinor": int(amt or 0),
        }
        for y, b, mode, cnt, amt in rows
    ]
