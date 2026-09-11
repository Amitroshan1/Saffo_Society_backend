"""Financial year & accounting period service."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.financial_year import AccountingPeriod, FinancialYear
from Schemas.billing import (
    AccountingPeriodCreate,
    AccountingPeriodListQueryParams,
    AccountingPeriodOut,
    FinancialYearCreate,
    FinancialYearListQueryParams,
    FinancialYearOut,
    FinancialYearUpdate,
    StatusNotesBody,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import (
    assert_fy_open,
    get_financial_year_in_society,
    get_period_in_society,
    require_society_id,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder


def _fy_dict(row: FinancialYear) -> Dict[str, Any]:
    return FinancialYearOut.from_orm(row).model_dump(mode="json")


def _period_dict(row: AccountingPeriod) -> Dict[str, Any]:
    return AccountingPeriodOut.from_orm(row).model_dump(mode="json")


def _month_periods(start: date, end: date) -> list[tuple[str, date, date]]:
    periods: list[tuple[str, date, date]] = []
    y, m = start.year, start.month
    while True:
        period_start = date(y, m, 1)
        last_day = calendar.monthrange(y, m)[1]
        period_end = date(y, m, last_day)
        if period_start < start:
            period_start = start
        if period_end > end:
            period_end = end
        if period_start > end:
            break
        periods.append((f"{y:04d}-{m:02d}", period_start, period_end))
        if period_end >= end:
            break
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return periods


async def create_financial_year(
    db: AsyncSession,
    body: FinancialYearCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    overlap = (
        await db.execute(
            select(FinancialYear).where(
                FinancialYear.society_id == society_id,
                FinancialYear.start_date <= body.endDate,
                FinancialYear.end_date >= body.startDate,
            )
        )
    ).scalars().first()
    if overlap:
        raise ApiError(422, "Financial year dates overlap an existing year")

    fy = FinancialYear(
        society_id=society_id,
        code=body.code,
        name=body.name,
        start_date=body.startDate,
        end_date=body.endDate,
        status="open",
        next_bill_seq=1,
        next_receipt_seq=1,
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(fy, actor_id)
    db.add(fy)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Financial year code already exists") from exc

    for period_key, p_start, p_end in _month_periods(body.startDate, body.endDate):
        period = AccountingPeriod(
            society_id=society_id,
            financial_year_id=fy.id,
            period_key=period_key,
            start_date=p_start,
            end_date=p_end,
            status="open",
            metadata_json={},
            is_active=True,
            version=1,
        )
        apply_create_audit(period, actor_id)
        db.add(period)

    await db.commit()
    await db.refresh(fy)
    periods = (
        await db.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.financial_year_id == fy.id)
            .order_by(AccountingPeriod.start_date.asc())
        )
    ).scalars().all()
    return {
        "financialYear": _fy_dict(fy),
        "periods": [_period_dict(p) for p in periods],
    }


async def list_financial_years(
    db: AsyncSession,
    query: FinancialYearListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(FinancialYear)
        .filter_eq("society_id", society_id)
        .search(query.search, "code", "name")
        .filter_eq("status", query.status)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("code", "name", "start_date", "end_date", "status", "created_at"),
            default="start_date",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "financialYears": [_fy_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_financial_year(
    db: AsyncSession, entity_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    fy = await get_financial_year_in_society(db, entity_id, society_id)
    periods = (
        await db.execute(
            select(AccountingPeriod)
            .where(
                AccountingPeriod.financial_year_id == fy.id,
                AccountingPeriod.society_id == society_id,
            )
            .order_by(AccountingPeriod.start_date.asc())
        )
    ).scalars().all()
    return {"financialYear": _fy_dict(fy), "periods": [_period_dict(p) for p in periods]}


async def update_financial_year(
    db: AsyncSession,
    entity_id: UUID,
    body: FinancialYearUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    fy = await get_financial_year_in_society(db, entity_id, society_id)
    assert_fy_open(fy)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        fy.name = data["name"]
    if "notes" in data:
        fy.notes = data["notes"]
    if "metadata" in data:
        fy.metadata_json = data["metadata"]
    apply_update_audit(fy, actor_id)
    await db.commit()
    await db.refresh(fy)
    return {"financialYear": _fy_dict(fy)}


async def close_financial_year(
    db: AsyncSession,
    entity_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    fy = await get_financial_year_in_society(db, entity_id, society_id)
    if fy.status == "closed":
        raise ApiError(422, "Financial year is already closed")
    open_periods = (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.financial_year_id == fy.id,
                AccountingPeriod.status == "open",
            )
        )
    ).scalars().all()
    now = utcnow()
    for period in open_periods:
        period.status = "closed"
        period.closed_at = now
        period.closed_by = actor_id
        apply_update_audit(period, actor_id)
    fy.status = "closed"
    fy.closed_at = now
    fy.closed_by = actor_id
    if body and body.notes:
        fy.notes = body.notes
    apply_update_audit(fy, actor_id)
    await db.commit()
    await db.refresh(fy)
    publish_simple(
        "BillingPeriodClosed",
        society_id=society_id,
        entity_type="financial_year",
        entity_id=fy.id,
        actor_id=actor_id,
        payload={"financialYearId": str(fy.id)},
    )
    return {"financialYear": _fy_dict(fy)}


async def create_accounting_period(
    db: AsyncSession,
    body: AccountingPeriodCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    fy = await get_financial_year_in_society(db, body.financialYearId, society_id)
    assert_fy_open(fy)
    if body.startDate < fy.start_date or body.endDate > fy.end_date:
        raise ApiError(422, "Period dates must fall within the financial year")
    period = AccountingPeriod(
        society_id=society_id,
        financial_year_id=fy.id,
        period_key=body.periodKey,
        start_date=body.startDate,
        end_date=body.endDate,
        status="open",
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(period, actor_id)
    db.add(period)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Accounting period key already exists") from exc
    await db.refresh(period)
    return {"accountingPeriod": _period_dict(period)}


async def list_accounting_periods(
    db: AsyncSession,
    query: AccountingPeriodListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(AccountingPeriod)
        .filter_eq("society_id", society_id)
        .filter_eq("financial_year_id", query.financial_year_id)
        .search(query.search, "period_key")
        .filter_eq("status", query.status)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("period_key", "start_date", "end_date", "status", "created_at"),
            default="start_date",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "accountingPeriods": [_period_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def close_accounting_period(
    db: AsyncSession,
    entity_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    period = await get_period_in_society(db, entity_id, society_id)
    if period.status == "closed":
        raise ApiError(422, "Accounting period is already closed")
    period.status = "closed"
    period.closed_at = utcnow()
    period.closed_by = actor_id
    if body and body.notes:
        period.notes = body.notes
    apply_update_audit(period, actor_id)
    await db.commit()
    await db.refresh(period)
    publish_simple(
        "BillingPeriodClosed",
        society_id=society_id,
        entity_type="accounting_period",
        entity_id=period.id,
        actor_id=actor_id,
        payload={"periodId": str(period.id)},
    )
    return {"accountingPeriod": _period_dict(period)}
