"""Maintenance bill lifecycle — create, generate, publish, fees, write-off."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.billing_cycle import BillingCycle
from Models.building import Building
from Models.charge_head import ChargeHead
from Models.discount_rule import DiscountRule
from Models.financial_year import AccountingPeriod
from Models.flat import Flat
from Models.late_fee_rule import LateFeeRule
from Models.maintenance_bill import BillLineItem, MaintenanceBill
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.wing import Wing
from Schemas.billing import (
    ApplyDiscountRequest,
    BillGenerateRequest,
    BillLineIn,
    BillLineOut,
    BillListQueryParams,
    MaintenanceBillCreate,
    MaintenanceBillOut,
    MaintenanceBillUpdate,
    StatusNotesBody,
    WriteOffRequest,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import (
    assert_fy_open,
    assert_period_open,
    get_bill_in_society,
    get_financial_year_in_society,
    get_period_in_society,
    next_bill_number,
    recompute_bill_totals,
    require_society_id,
    update_bill_status_from_amounts,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder

EDITABLE_STATUSES = {"draft", "generated"}
PUBLISHABLE_STATUSES = {"draft", "generated"}
CANCELABLE_STATUSES = {"draft", "generated", "published", "overdue"}
WRITEOFF_STATUSES = {"published", "overdue", "partially_paid"}
OUTSTANDING_STATUSES = {"published", "partially_paid", "overdue"}


async def _load_context_maps(
    db: AsyncSession, bills: list[MaintenanceBill]
) -> tuple[dict, dict, dict, dict]:
    resident_ids = {b.resident_id for b in bills}
    flat_ids = {b.flat_id for b in bills}
    wing_ids = {b.wing_id for b in bills}
    building_ids = {b.building_id for b in bills}
    residents = {}
    if resident_ids:
        r = await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
        residents = {x.id: x for x in r.scalars().all()}
    flats = {}
    if flat_ids:
        r = await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
        flats = {x.id: x for x in r.scalars().all()}
    wings = {}
    if wing_ids:
        r = await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))
        wings = {x.id: x for x in r.scalars().all()}
    buildings = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {x.id: x for x in r.scalars().all()}
    return residents, flats, wings, buildings


async def _load_lines(
    db: AsyncSession, bill_ids: list[UUID]
) -> dict[UUID, list[BillLineItem]]:
    lines_map: dict[UUID, list[BillLineItem]] = {bid: [] for bid in bill_ids}
    if not bill_ids:
        return lines_map
    rows = (
        await db.execute(
            select(BillLineItem)
            .where(
                BillLineItem.bill_id.in_(bill_ids),
                BillLineItem.is_active.is_(True),
            )
            .order_by(BillLineItem.line_no.asc())
        )
    ).scalars().all()
    for ln in rows:
        lines_map.setdefault(ln.bill_id, []).append(ln)
    return lines_map


async def _charge_head_map(db: AsyncSession, lines: list[BillLineItem]) -> dict[UUID, ChargeHead]:
    ids = {ln.charge_head_id for ln in lines}
    if not ids:
        return {}
    rows = (await db.execute(select(ChargeHead).where(ChargeHead.id.in_(ids)))).scalars().all()
    return {x.id: x for x in rows}


def _bill_dict(
    bill: MaintenanceBill,
    *,
    resident: Optional[Resident] = None,
    flat: Optional[Flat] = None,
    wing: Optional[Wing] = None,
    building: Optional[Building] = None,
    lines: Optional[list[BillLineItem]] = None,
    charge_heads: Optional[dict[UUID, ChargeHead]] = None,
) -> Dict[str, Any]:
    line_outs = None
    if lines is not None:
        ch = charge_heads or {}
        line_outs = [
            BillLineOut.from_orm(
                ln,
                charge_head_code=ch[ln.charge_head_id].code if ln.charge_head_id in ch else None,
                charge_head_name=ch[ln.charge_head_id].name if ln.charge_head_id in ch else None,
            )
            for ln in lines
        ]
    return MaintenanceBillOut.from_orm(
        bill,
        resident_name=resident.name if resident else None,
        flat_no=flat.flat_no if flat else None,
        wing_code=wing.code if wing else None,
        building_name=building.name if building else None,
        lines=line_outs,
    ).model_dump(mode="json")


def _line_total(line_in: BillLineIn) -> int:
    return max(0, line_in.quantity * line_in.unitAmountMinor - line_in.discountMinor)


async def _create_lines(
    db: AsyncSession,
    bill: MaintenanceBill,
    lines: List[BillLineIn],
    *,
    actor_id: UUID,
    society_id: UUID,
) -> list[BillLineItem]:
    created: list[BillLineItem] = []
    for idx, item in enumerate(lines, start=1):
        head = (
            await db.execute(
                select(ChargeHead).where(
                    ChargeHead.id == item.chargeHeadId,
                    ChargeHead.society_id == society_id,
                )
            )
        ).scalar_one_or_none()
        if not head:
            raise ApiError(404, f"Charge head not found: {item.chargeHeadId}")
        description = item.description or head.name
        ln = BillLineItem(
            society_id=society_id,
            bill_id=bill.id,
            charge_head_id=head.id,
            line_no=idx,
            description=description,
            quantity=item.quantity,
            unit_amount_minor=item.unitAmountMinor,
            line_total_minor=_line_total(item),
            tax_minor=item.taxMinor,
            discount_minor=item.discountMinor,
            is_penalty=item.isPenalty,
            is_discount=item.isDiscount,
            notes=item.notes,
            metadata_json=item.metadata,
            is_active=True,
            version=1,
        )
        apply_create_audit(ln, actor_id)
        db.add(ln)
        created.append(ln)
    await db.flush()
    return created


async def create_bill(
    db: AsyncSession,
    body: MaintenanceBillCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    occupancy = (
        await db.execute(
            select(Occupancy).where(
                Occupancy.id == body.occupancyId,
                Occupancy.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if not occupancy:
        raise ApiError(404, "Occupancy not found")
    if occupancy.status != "active" or not occupancy.is_active:
        raise ApiError(422, "Cannot bill an inactive occupancy")

    fy = await get_financial_year_in_society(db, body.financialYearId, society_id)
    assert_fy_open(fy)
    period = None
    if body.accountingPeriodId:
        period = await get_period_in_society(db, body.accountingPeriodId, society_id)
        assert_period_open(period)
        if period.financial_year_id != fy.id:
            raise ApiError(422, "Accounting period does not belong to financial year")

    bill_number = await next_bill_number(db, fy)
    bill = MaintenanceBill(
        society_id=society_id,
        building_id=occupancy.building_id,
        wing_id=occupancy.wing_id,
        flat_id=occupancy.flat_id,
        occupancy_id=occupancy.id,
        resident_id=occupancy.resident_id,
        billing_cycle_id=body.billingCycleId,
        financial_year_id=fy.id,
        accounting_period_id=period.id if period else None,
        bill_number=bill_number,
        title=body.title,
        status="draft",
        bill_date=body.billDate or date.today(),
        period_from=body.periodFrom,
        period_to=body.periodTo,
        due_date=body.dueDate,
        currency=body.currency,
        source="manual",
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(bill, actor_id)
    db.add(bill)
    await db.flush()
    lines = await _create_lines(db, bill, body.lines, actor_id=actor_id, society_id=society_id)
    recompute_bill_totals(bill, lines)
    bill.status = "generated"
    apply_update_audit(bill, actor_id)
    await db.commit()
    await db.refresh(bill)
    publish_simple(
        "BillGenerated",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={
            "billId": str(bill.id),
            "occupancyId": str(bill.occupancy_id),
            "netMinor": bill.net_minor,
        },
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def list_bills(
    db: AsyncSession,
    query: BillListQueryParams,
    *,
    actor_society_id: UUID | None,
    resident_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    rid = resident_id or query.resident_id
    builder = (
        ListQueryBuilder(MaintenanceBill)
        .filter_eq("society_id", society_id)
        .search(query.search, "bill_number", "title")
        .filter_eq("status", query.status)
        .filter_eq("occupancy_id", query.occupancy_id)
        .filter_eq("resident_id", rid)
        .filter_eq("flat_id", query.flat_id)
        .filter_eq("building_id", query.building_id)
        .filter_eq("wing_id", query.wing_id)
        .filter_eq("billing_cycle_id", query.billing_cycle_id)
        .filter_eq("financial_year_id", query.financial_year_id)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            (
                "created_at",
                "due_date",
                "bill_date",
                "status",
                "bill_number",
                "outstanding_minor",
                "net_minor",
            ),
            default="created_at",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    residents, flats, wings, buildings = await _load_context_maps(db, items)
    return {
        "bills": [
            _bill_dict(
                b,
                resident=residents.get(b.resident_id),
                flat=flats.get(b.flat_id),
                wing=wings.get(b.wing_id),
                building=buildings.get(b.building_id),
            )
            for b in items
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_bill(
    db: AsyncSession, bill_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    residents, flats, wings, buildings = await _load_context_maps(db, [bill])
    lines_map = await _load_lines(db, [bill.id])
    lines = lines_map.get(bill.id, [])
    charge_heads = await _charge_head_map(db, lines)
    return {
        "bill": _bill_dict(
            bill,
            resident=residents.get(bill.resident_id),
            flat=flats.get(bill.flat_id),
            wing=wings.get(bill.wing_id),
            building=buildings.get(bill.building_id),
            lines=lines,
            charge_heads=charge_heads,
        )
    }


async def update_draft_bill(
    db: AsyncSession,
    bill_id: UUID,
    body: MaintenanceBillUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status not in EDITABLE_STATUSES:
        raise ApiError(422, "Only draft/generated bills can be updated")
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "title": "title",
        "billDate": "bill_date",
        "periodFrom": "period_from",
        "periodTo": "period_to",
        "dueDate": "due_date",
        "notes": "notes",
        "metadata": "metadata_json",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data and api_key != "lines":
            setattr(bill, orm_key, data[api_key])
    if "lines" in data and body.lines is not None:
        existing = (
            await db.execute(
                select(BillLineItem).where(BillLineItem.bill_id == bill.id)
            )
        ).scalars().all()
        for ln in existing:
            ln.is_active = False
            apply_update_audit(ln, actor_id)
        lines = await _create_lines(
            db, bill, body.lines, actor_id=actor_id, society_id=society_id
        )
        recompute_bill_totals(bill, lines)
    apply_update_audit(bill, actor_id)
    await db.commit()
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def generate_bills(
    db: AsyncSession,
    body: BillGenerateRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    cycle = (
        await db.execute(
            select(BillingCycle).where(
                BillingCycle.id == body.cycleId,
                BillingCycle.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if not cycle:
        raise ApiError(404, "Billing cycle not found")

    fy = await get_financial_year_in_society(db, body.financialYearId, society_id)
    assert_fy_open(fy)
    period = None
    if body.accountingPeriodId:
        period = await get_period_in_society(db, body.accountingPeriodId, society_id)
        assert_period_open(period)
        if period.financial_year_id != fy.id:
            raise ApiError(422, "Accounting period does not belong to financial year")
    else:
        period = (
            await db.execute(
                select(AccountingPeriod).where(
                    AccountingPeriod.society_id == society_id,
                    AccountingPeriod.financial_year_id == fy.id,
                    AccountingPeriod.status == "open",
                    AccountingPeriod.start_date <= body.periodFrom,
                    AccountingPeriod.end_date >= body.periodFrom,
                )
            )
        ).scalars().first()
        if period:
            assert_period_open(period)

    heads = (
        await db.execute(
            select(ChargeHead).where(
                ChargeHead.id.in_(body.chargeHeadIds),
                ChargeHead.society_id == society_id,
                ChargeHead.is_active.is_(True),
            )
        )
    ).scalars().all()
    if len(heads) != len(set(body.chargeHeadIds)):
        raise ApiError(422, "One or more charge heads are invalid or inactive")
    heads_by_id = {h.id: h for h in heads}

    occ_stmt = select(Occupancy).where(
        Occupancy.society_id == society_id,
        Occupancy.status == "active",
        Occupancy.is_active.is_(True),
        Occupancy.role != "domestic_help",
    )
    if body.occupancyIds:
        occ_stmt = occ_stmt.where(Occupancy.id.in_(body.occupancyIds))
    occupancies = (await db.execute(occ_stmt)).scalars().all()

    by_flat: dict[UUID, list[Occupancy]] = {}
    for occ in occupancies:
        by_flat.setdefault(occ.flat_id, []).append(occ)

    selected: list[Occupancy] = []
    exceptions: list[dict] = []
    for flat_id, group in by_flat.items():
        primaries = [o for o in group if o.is_primary]
        if len(primaries) == 1:
            selected.append(primaries[0])
        elif len(primaries) == 0 and len(group) == 1:
            selected.append(group[0])
        elif len(primaries) > 1:
            exceptions.append(
                {"flatId": str(flat_id), "reason": "Multiple primary occupancies"}
            )
        else:
            exceptions.append(
                {"flatId": str(flat_id), "reason": "No primary occupancy to bill"}
            )

    auto_publish = body.autoPublish or cycle.auto_publish
    title = body.title or f"{cycle.name} {body.periodFrom.isoformat()} – {body.periodTo.isoformat()}"
    created_bills: list[MaintenanceBill] = []
    skipped: list[dict] = []

    for occ in selected:
        dup = (
            await db.execute(
                select(MaintenanceBill).where(
                    MaintenanceBill.society_id == society_id,
                    MaintenanceBill.occupancy_id == occ.id,
                    MaintenanceBill.period_from == body.periodFrom,
                    MaintenanceBill.period_to == body.periodTo,
                    MaintenanceBill.billing_cycle_id == cycle.id,
                    MaintenanceBill.status.notin_(("cancelled",)),
                )
            )
        ).scalar_one_or_none()
        if dup:
            skipped.append(
                {
                    "occupancyId": str(occ.id),
                    "reason": "Duplicate bill for period/cycle",
                    "existingBillId": str(dup.id),
                }
            )
            continue

        bill_number = await next_bill_number(db, fy)
        bill = MaintenanceBill(
            society_id=society_id,
            building_id=occ.building_id,
            wing_id=occ.wing_id,
            flat_id=occ.flat_id,
            occupancy_id=occ.id,
            resident_id=occ.resident_id,
            billing_cycle_id=cycle.id,
            financial_year_id=fy.id,
            accounting_period_id=period.id if period else None,
            bill_number=bill_number,
            title=title,
            status="generated",
            bill_date=date.today(),
            period_from=body.periodFrom,
            period_to=body.periodTo,
            due_date=body.dueDate,
            currency="INR",
            source="system",
            metadata_json={},
            is_active=True,
            version=1,
        )
        apply_create_audit(bill, actor_id)
        db.add(bill)
        await db.flush()

        line_ins = [
            BillLineIn(
                chargeHeadId=hid,
                unitAmountMinor=heads_by_id[hid].default_amount_minor,
                description=heads_by_id[hid].name,
            )
            for hid in body.chargeHeadIds
        ]
        lines = await _create_lines(
            db, bill, line_ins, actor_id=actor_id, society_id=society_id
        )
        recompute_bill_totals(bill, lines)
        publish_simple(
            "BillGenerated",
            society_id=society_id,
            entity_type="maintenance_bill",
            entity_id=bill.id,
            actor_id=actor_id,
            payload={
                "billId": str(bill.id),
                "occupancyId": str(bill.occupancy_id),
                "netMinor": bill.net_minor,
            },
        )
        if auto_publish:
            bill.status = "published"
            bill.published_at = utcnow()
            publish_simple(
                "BillPublished",
                society_id=society_id,
                entity_type="maintenance_bill",
                entity_id=bill.id,
                actor_id=actor_id,
                payload={
                    "billId": str(bill.id),
                    "dueDate": bill.due_date.isoformat(),
                    "residentId": str(bill.resident_id),
                },
            )
        created_bills.append(bill)

    cycle.last_run_at = utcnow()
    apply_update_audit(cycle, actor_id)
    await db.commit()

    residents, flats, wings, buildings = await _load_context_maps(db, created_bills)
    return {
        "createdCount": len(created_bills),
        "skippedCount": len(skipped),
        "exceptionCount": len(exceptions),
        "bills": [
            _bill_dict(
                b,
                resident=residents.get(b.resident_id),
                flat=flats.get(b.flat_id),
                wing=wings.get(b.wing_id),
                building=buildings.get(b.building_id),
            )
            for b in created_bills
        ],
        "skipped": skipped,
        "exceptions": exceptions,
    }


async def publish_bill(
    db: AsyncSession,
    bill_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status not in PUBLISHABLE_STATUSES:
        raise ApiError(422, "Bill cannot be published from current status")
    bill.status = "published"
    bill.published_at = utcnow()
    if body and body.notes:
        bill.notes = body.notes
    apply_update_audit(bill, actor_id)
    await db.commit()
    publish_simple(
        "BillPublished",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={
            "billId": str(bill.id),
            "dueDate": bill.due_date.isoformat(),
            "residentId": str(bill.resident_id),
        },
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def cancel_bill(
    db: AsyncSession,
    bill_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status not in CANCELABLE_STATUSES:
        raise ApiError(422, "Bill cannot be cancelled from current status")
    if bill.paid_minor > 0:
        raise ApiError(422, "Cannot cancel a bill with payments; reverse payments first")
    bill.status = "cancelled"
    bill.cancelled_at = utcnow()
    bill.is_active = False
    if body and body.notes:
        bill.notes = body.notes
    apply_update_audit(bill, actor_id)
    await db.commit()
    publish_simple(
        "BillCancelled",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={"billId": str(bill.id), "reason": body.notes if body else None},
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def write_off_bill(
    db: AsyncSession,
    bill_id: UUID,
    body: WriteOffRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status not in WRITEOFF_STATUSES:
        raise ApiError(422, "Bill cannot be written off from current status")
    if bill.outstanding_minor <= 0:
        raise ApiError(422, "Bill has no outstanding amount to write off")
    amount = bill.outstanding_minor
    bill.write_off_reason = body.reason
    bill.written_off_at = utcnow()
    bill.status = "write_off"
    bill.outstanding_minor = 0
    if body.notes:
        bill.notes = body.notes
    apply_update_audit(bill, actor_id)
    await db.commit()
    publish_simple(
        "BillWrittenOff",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={
            "billId": str(bill.id),
            "amountMinor": amount,
            "reason": body.reason,
        },
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


def _calc_late_fee(rule: LateFeeRule, bill: MaintenanceBill, today: date) -> int:
    grace_end = bill.due_date + timedelta(days=rule.grace_days)
    if today <= grace_end:
        return 0
    base = bill.outstanding_minor if rule.apply_on == "outstanding" else bill.net_minor
    if base <= 0:
        return 0
    if rule.fee_type == "fixed":
        amount = rule.fixed_amount_minor or 0
    elif rule.fee_type == "percentage":
        amount = (base * (rule.percentage_bps or 0)) // 10000
    else:
        days = (today - grace_end).days
        amount = days * (rule.daily_amount_minor or 0)
    if rule.max_penalty_minor is not None:
        amount = min(amount, rule.max_penalty_minor)
    return max(0, amount)


async def apply_late_fee(
    db: AsyncSession,
    bill_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status not in OUTSTANDING_STATUSES:
        raise ApiError(422, "Late fee can only be applied to outstanding bills")
    today = date.today()
    rules = (
        await db.execute(
            select(LateFeeRule)
            .where(
                LateFeeRule.society_id == society_id,
                LateFeeRule.is_active.is_(True),
            )
            .order_by(LateFeeRule.priority.desc())
        )
    ).scalars().all()
    matching = []
    for rule in rules:
        if rule.billing_cycle_id and rule.billing_cycle_id != bill.billing_cycle_id:
            continue
        if rule.effective_from and today < rule.effective_from:
            continue
        if rule.effective_to and today > rule.effective_to:
            continue
        matching.append(rule)
    if not matching:
        raise ApiError(422, "No matching late fee rule found")
    rule = matching[0]
    already = (
        await db.execute(
            select(BillLineItem).where(
                BillLineItem.bill_id == bill.id,
                BillLineItem.is_penalty.is_(True),
                BillLineItem.is_active.is_(True),
            )
        )
    ).scalars().first()
    if already and (already.metadata_json or {}).get("lateFeeRuleId") == str(rule.id):
        raise ApiError(422, "Late fee already applied for this rule")

    amount = _calc_late_fee(rule, bill, today)
    if amount <= 0:
        raise ApiError(422, "Late fee amount is zero for current bill state")

    head_id = rule.charge_head_id
    if not head_id:
        head = (
            await db.execute(
                select(ChargeHead).where(
                    ChargeHead.society_id == society_id,
                    ChargeHead.is_active.is_(True),
                ).order_by(ChargeHead.display_order.asc())
            )
        ).scalars().first()
        if not head:
            raise ApiError(422, "No charge head available for late fee line")
        head_id = head.id

    lines_map = await _load_lines(db, [bill.id])
    lines = list(lines_map.get(bill.id, []))
    ln = BillLineItem(
        society_id=society_id,
        bill_id=bill.id,
        charge_head_id=head_id,
        line_no=len(lines) + 1,
        description=f"Late fee — {rule.name}",
        quantity=1,
        unit_amount_minor=amount,
        line_total_minor=amount,
        tax_minor=0,
        discount_minor=0,
        is_penalty=True,
        is_discount=False,
        notes=body.notes if body else None,
        metadata_json={"lateFeeRuleId": str(rule.id)},
        is_active=True,
        version=1,
    )
    apply_create_audit(ln, actor_id)
    db.add(ln)
    lines.append(ln)
    recompute_bill_totals(bill, lines)
    update_bill_status_from_amounts(bill)
    apply_update_audit(bill, actor_id)
    await db.commit()
    publish_simple(
        "LateFeeApplied",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={
            "billId": str(bill.id),
            "amountMinor": amount,
            "ruleId": str(rule.id),
        },
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def apply_discount(
    db: AsyncSession,
    bill_id: UUID,
    body: ApplyDiscountRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    bill = await get_bill_in_society(db, bill_id, society_id)
    if bill.status in {"cancelled", "write_off", "paid"}:
        raise ApiError(422, "Cannot apply discount to this bill")

    rule = None
    amount = body.amountMinor or 0
    if body.discountRuleId:
        rule = (
            await db.execute(
                select(DiscountRule).where(
                    DiscountRule.id == body.discountRuleId,
                    DiscountRule.society_id == society_id,
                    DiscountRule.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not rule:
            raise ApiError(404, "Discount rule not found")
        if rule.max_uses is not None and rule.uses_count >= rule.max_uses:
            raise ApiError(422, "Discount rule usage limit reached")
        if rule.discount_type == "fixed":
            amount = rule.fixed_amount_minor or 0
        else:
            amount = (bill.gross_minor * (rule.percentage_bps or 0)) // 10000
        rule.uses_count += 1
        apply_update_audit(rule, actor_id)

    if amount <= 0:
        raise ApiError(422, "Discount amount must be positive")
    if amount > bill.net_minor:
        raise ApiError(422, "Discount cannot exceed bill net amount")

    head_id = rule.charge_head_id if rule and rule.charge_head_id else None
    if not head_id:
        head = (
            await db.execute(
                select(ChargeHead)
                .where(ChargeHead.society_id == society_id, ChargeHead.is_active.is_(True))
                .order_by(ChargeHead.display_order.asc())
            )
        ).scalars().first()
        if not head:
            raise ApiError(422, "No charge head available for discount line")
        head_id = head.id

    lines_map = await _load_lines(db, [bill.id])
    lines = list(lines_map.get(bill.id, []))
    ln = BillLineItem(
        society_id=society_id,
        bill_id=bill.id,
        charge_head_id=head_id,
        line_no=len(lines) + 1,
        description=body.description or (f"Discount — {rule.name}" if rule else "Discount"),
        quantity=1,
        unit_amount_minor=amount,
        line_total_minor=amount,
        tax_minor=0,
        discount_minor=0,
        is_penalty=False,
        is_discount=True,
        notes=body.notes,
        metadata_json={"discountRuleId": str(rule.id)} if rule else {},
        is_active=True,
        version=1,
    )
    apply_create_audit(ln, actor_id)
    db.add(ln)
    lines.append(ln)
    recompute_bill_totals(bill, lines)
    update_bill_status_from_amounts(bill)
    apply_update_audit(bill, actor_id)
    await db.commit()
    publish_simple(
        "DiscountApplied",
        society_id=society_id,
        entity_type="maintenance_bill",
        entity_id=bill.id,
        actor_id=actor_id,
        payload={
            "billId": str(bill.id),
            "amountMinor": amount,
            "ruleId": str(rule.id) if rule else None,
        },
    )
    return await get_bill(db, bill.id, actor_society_id=society_id)


async def mark_overdue_bills(
    db: AsyncSession, *, actor_society_id: UUID | None, actor_id: UUID | None = None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()
    bills = (
        await db.execute(
            select(MaintenanceBill).where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status == "published",
                MaintenanceBill.due_date < today,
                MaintenanceBill.outstanding_minor > 0,
                MaintenanceBill.is_active.is_(True),
            )
        )
    ).scalars().all()
    updated = 0
    for bill in bills:
        bill.status = "overdue"
        if actor_id:
            apply_update_audit(bill, actor_id)
        publish_simple(
            "BillOverdue",
            society_id=society_id,
            entity_type="maintenance_bill",
            entity_id=bill.id,
            actor_id=actor_id,
            payload={
                "billId": str(bill.id),
                "outstandingMinor": bill.outstanding_minor,
            },
        )
        updated += 1
    await db.commit()
    return {"updatedCount": updated}
