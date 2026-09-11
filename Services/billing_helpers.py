"""Billing helpers — FY/period locks, sequences, totals, resident resolve."""

from __future__ import annotations

from datetime import date
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.financial_year import AccountingPeriod, FinancialYear
from Models.maintenance_bill import BillLineItem, MaintenanceBill
from Models.occupancy import Occupancy
from Models.resident import Resident
from Utils.errors import ApiError


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def get_financial_year_in_society(
    db: AsyncSession, fy_id: UUID, society_id: UUID
) -> FinancialYear:
    result = await db.execute(
        select(FinancialYear).where(
            FinancialYear.id == fy_id,
            FinancialYear.society_id == society_id,
        )
    )
    fy = result.scalar_one_or_none()
    if not fy:
        raise ApiError(404, "Financial year not found")
    return fy


async def get_period_in_society(
    db: AsyncSession, period_id: UUID, society_id: UUID
) -> AccountingPeriod:
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.society_id == society_id,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise ApiError(404, "Accounting period not found")
    return period


async def get_open_financial_year(
    db: AsyncSession, society_id: UUID, *, on_date: date | None = None
) -> FinancialYear:
    stmt = select(FinancialYear).where(
        FinancialYear.society_id == society_id,
        FinancialYear.status == "open",
        FinancialYear.is_active.is_(True),
    )
    if on_date is not None:
        stmt = stmt.where(
            FinancialYear.start_date <= on_date,
            FinancialYear.end_date >= on_date,
        )
    stmt = stmt.order_by(FinancialYear.start_date.desc())
    fy = (await db.execute(stmt)).scalars().first()
    if not fy:
        raise ApiError(404, "No open financial year found")
    return fy


async def get_open_period(
    db: AsyncSession,
    society_id: UUID,
    *,
    financial_year_id: UUID | None = None,
    on_date: date | None = None,
) -> AccountingPeriod:
    stmt = select(AccountingPeriod).where(
        AccountingPeriod.society_id == society_id,
        AccountingPeriod.status == "open",
        AccountingPeriod.is_active.is_(True),
    )
    if financial_year_id is not None:
        stmt = stmt.where(AccountingPeriod.financial_year_id == financial_year_id)
    if on_date is not None:
        stmt = stmt.where(
            AccountingPeriod.start_date <= on_date,
            AccountingPeriod.end_date >= on_date,
        )
    stmt = stmt.order_by(AccountingPeriod.start_date.desc())
    period = (await db.execute(stmt)).scalars().first()
    if not period:
        raise ApiError(404, "No open accounting period found")
    return period


def assert_fy_open(fy: FinancialYear) -> None:
    if fy.status != "open":
        raise ApiError(422, "Financial year is not open")


def assert_period_open(period: AccountingPeriod) -> None:
    if period.status != "open":
        raise ApiError(422, "Accounting period is not open")


async def next_bill_number(db: AsyncSession, fy: FinancialYear) -> str:
    locked = (
        await db.execute(
            select(FinancialYear)
            .where(FinancialYear.id == fy.id)
            .with_for_update()
        )
    ).scalar_one()
    seq = locked.next_bill_seq
    locked.next_bill_seq = seq + 1
    await db.flush()
    return f"{locked.code}-BILL-{seq:05d}"


async def next_receipt_number(db: AsyncSession, fy: FinancialYear) -> str:
    locked = (
        await db.execute(
            select(FinancialYear)
            .where(FinancialYear.id == fy.id)
            .with_for_update()
        )
    ).scalar_one()
    seq = locked.next_receipt_seq
    locked.next_receipt_seq = seq + 1
    await db.flush()
    return f"{locked.code}-RCPT-{seq:05d}"


async def next_payment_number(db: AsyncSession, fy: FinancialYear) -> str:
    locked = (
        await db.execute(
            select(FinancialYear)
            .where(FinancialYear.id == fy.id)
            .with_for_update()
        )
    ).scalar_one()
    meta = dict(locked.metadata_json or {})
    seq = int(meta.get("next_payment_seq", 1))
    meta["next_payment_seq"] = seq + 1
    locked.metadata_json = meta
    await db.flush()
    return f"{locked.code}-PAY-{seq:05d}"


def recompute_bill_totals(bill: MaintenanceBill, lines: Sequence[BillLineItem]) -> None:
    active = [ln for ln in lines if ln.is_active]
    gross = 0
    discount = 0
    penalty = 0
    tax = 0
    for ln in active:
        if ln.is_discount:
            discount += ln.line_total_minor + ln.discount_minor
        elif ln.is_penalty:
            penalty += ln.line_total_minor
            tax += ln.tax_minor
        else:
            gross += ln.line_total_minor
            discount += ln.discount_minor
            tax += ln.tax_minor
    bill.gross_minor = max(0, gross)
    bill.discount_minor = max(0, discount)
    bill.penalty_minor = max(0, penalty)
    bill.tax_minor = max(0, tax)
    bill.net_minor = max(0, bill.gross_minor - bill.discount_minor + bill.penalty_minor + bill.tax_minor)
    bill.outstanding_minor = max(0, bill.net_minor - bill.paid_minor)


def update_bill_status_from_amounts(bill: MaintenanceBill) -> None:
    if bill.status in {"cancelled", "write_off", "draft", "generated"}:
        return
    if bill.outstanding_minor <= 0 and bill.paid_minor >= bill.net_minor:
        bill.status = "paid"
        bill.outstanding_minor = 0
    elif bill.paid_minor > 0 and bill.outstanding_minor > 0:
        bill.status = "partially_paid"
    elif bill.status in {"published", "overdue", "partially_paid", "paid"}:
        if bill.outstanding_minor > 0 and bill.due_date < date.today() and bill.paid_minor == 0:
            bill.status = "overdue"
        elif bill.outstanding_minor > 0 and bill.paid_minor == 0 and bill.status != "overdue":
            if bill.published_at is not None:
                bill.status = "published" if bill.due_date >= date.today() else "overdue"


async def resolve_resident_for_user(
    db: AsyncSession, *, actor_id: UUID, society_id: UUID
) -> tuple[Resident, Occupancy]:
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

    occupancy = (
        await db.execute(
            select(Occupancy)
            .where(
                Occupancy.society_id == society_id,
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
            .order_by(Occupancy.is_primary.desc(), Occupancy.move_in_date.desc())
        )
    ).scalars().first()
    if not occupancy:
        raise ApiError(404, "Active occupancy not found for resident")
    return resident, occupancy


async def sum_resident_outstanding(
    db: AsyncSession, *, society_id: UUID, resident_id: UUID
) -> int:
    from sqlalchemy import func

    result = await db.execute(
        select(func.coalesce(func.sum(MaintenanceBill.outstanding_minor), 0)).where(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.resident_id == resident_id,
            MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
            MaintenanceBill.is_active.is_(True),
        )
    )
    return int(result.scalar_one() or 0)


async def get_bill_in_society(
    db: AsyncSession, bill_id: UUID, society_id: UUID
) -> MaintenanceBill:
    result = await db.execute(
        select(MaintenanceBill).where(
            MaintenanceBill.id == bill_id,
            MaintenanceBill.society_id == society_id,
        )
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise ApiError(404, "Bill not found")
    return bill
