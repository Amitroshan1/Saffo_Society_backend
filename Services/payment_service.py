"""Payment, allocation & receipt service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.maintenance_bill import MaintenanceBill
from Models.payment import Payment, PaymentAllocation, Receipt
from Models.resident import Resident
from Schemas.billing import (
    PaymentAllocateRequest,
    PaymentAllocationIn,
    PaymentAllocationOut,
    PaymentCreate,
    PaymentListQueryParams,
    PaymentOut,
    ReceiptListQueryParams,
    ReceiptOut,
    StatusNotesBody,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import (
    assert_fy_open,
    assert_period_open,
    get_bill_in_society,
    get_financial_year_in_society,
    get_period_in_society,
    next_payment_number,
    next_receipt_number,
    require_society_id,
    update_bill_status_from_amounts,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder

ALLOCATABLE_BILL_STATUSES = {"published", "partially_paid", "overdue"}
IMMEDIATE_CLEAR_MODES = {"cash"}


def _payment_dict(
    payment: Payment,
    *,
    resident_name: Optional[str] = None,
    allocations: Optional[list[PaymentAllocation]] = None,
) -> Dict[str, Any]:
    alloc_outs = None
    if allocations is not None:
        alloc_outs = [PaymentAllocationOut.from_orm(a) for a in allocations]
    return PaymentOut.from_orm(
        payment, resident_name=resident_name, allocations=alloc_outs
    ).model_dump(mode="json")


def _receipt_dict(receipt: Receipt, *, resident_name: Optional[str] = None) -> Dict[str, Any]:
    return ReceiptOut.from_orm(receipt, resident_name=resident_name).model_dump(mode="json")


async def _get_payment(db: AsyncSession, payment_id: UUID, society_id: UUID) -> Payment:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.society_id == society_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise ApiError(404, "Payment not found")
    return payment


async def _get_receipt(db: AsyncSession, receipt_id: UUID, society_id: UUID) -> Receipt:
    result = await db.execute(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.society_id == society_id)
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise ApiError(404, "Receipt not found")
    return receipt


async def _resident_names(db: AsyncSession, resident_ids: set[UUID]) -> dict[UUID, str]:
    if not resident_ids:
        return {}
    rows = (await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))).scalars().all()
    return {r.id: r.name for r in rows}


async def _load_allocations(
    db: AsyncSession, payment_ids: list[UUID]
) -> dict[UUID, list[PaymentAllocation]]:
    result: dict[UUID, list[PaymentAllocation]] = {pid: [] for pid in payment_ids}
    if not payment_ids:
        return result
    rows = (
        await db.execute(
            select(PaymentAllocation).where(
                PaymentAllocation.payment_id.in_(payment_ids),
                PaymentAllocation.is_active.is_(True),
            )
        )
    ).scalars().all()
    for a in rows:
        result.setdefault(a.payment_id, []).append(a)
    return result


async def _apply_allocation_to_bill(
    db: AsyncSession,
    bill: MaintenanceBill,
    amount: int,
    *,
    actor_id: UUID,
) -> None:
    if bill.status not in ALLOCATABLE_BILL_STATUSES:
        raise ApiError(422, f"Bill {bill.bill_number} is not allocatable")
    if amount > bill.outstanding_minor:
        raise ApiError(422, f"Allocation exceeds outstanding for bill {bill.bill_number}")
    bill.paid_minor += amount
    bill.outstanding_minor = max(0, bill.net_minor - bill.paid_minor)
    update_bill_status_from_amounts(bill)
    apply_update_audit(bill, actor_id)


async def _create_allocations(
    db: AsyncSession,
    payment: Payment,
    allocations: List[PaymentAllocationIn],
    *,
    actor_id: UUID,
    society_id: UUID,
    apply_to_bills: bool,
) -> list[PaymentAllocation]:
    total = sum(a.amountMinor for a in allocations)
    if total > payment.unallocated_minor:
        raise ApiError(422, "Allocation total exceeds unallocated payment amount")
    created: list[PaymentAllocation] = []
    now = utcnow()
    for item in allocations:
        bill = None
        if item.allocationType == "bill":
            if not item.billId:
                raise ApiError(422, "billId required for bill allocation")
            bill = await get_bill_in_society(db, item.billId, society_id)
            if bill.resident_id != payment.resident_id:
                raise ApiError(422, "Bill resident does not match payment resident")
            if apply_to_bills:
                await _apply_allocation_to_bill(
                    db, bill, item.amountMinor, actor_id=actor_id
                )
        alloc = PaymentAllocation(
            society_id=society_id,
            payment_id=payment.id,
            bill_id=bill.id if bill else None,
            allocation_type=item.allocationType,
            amount_minor=item.amountMinor,
            allocated_at=now,
            notes=item.notes,
            metadata_json={},
            is_active=True,
            version=1,
        )
        apply_create_audit(alloc, actor_id)
        db.add(alloc)
        created.append(alloc)
        payment.unallocated_minor -= item.amountMinor
    return created


async def _auto_allocate_fifo(
    db: AsyncSession,
    payment: Payment,
    *,
    actor_id: UUID,
    society_id: UUID,
) -> list[PaymentAllocation]:
    stmt = (
        select(MaintenanceBill)
        .where(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.resident_id == payment.resident_id,
            MaintenanceBill.status.in_(tuple(ALLOCATABLE_BILL_STATUSES)),
            MaintenanceBill.outstanding_minor > 0,
            MaintenanceBill.is_active.is_(True),
        )
        .order_by(MaintenanceBill.due_date.asc(), MaintenanceBill.created_at.asc())
    )
    if payment.occupancy_id:
        stmt = stmt.where(MaintenanceBill.occupancy_id == payment.occupancy_id)
    bills = (await db.execute(stmt)).scalars().all()
    remaining = payment.unallocated_minor
    items: list[PaymentAllocationIn] = []
    for bill in bills:
        if remaining <= 0:
            break
        amount = min(remaining, bill.outstanding_minor)
        items.append(
            PaymentAllocationIn(
                billId=bill.id, amountMinor=amount, allocationType="bill"
            )
        )
        remaining -= amount
    if remaining > 0:
        items.append(
            PaymentAllocationIn(
                amountMinor=remaining, allocationType="advance"
            )
        )
    if not items:
        return []
    return await _create_allocations(
        db,
        payment,
        items,
        actor_id=actor_id,
        society_id=society_id,
        apply_to_bills=True,
    )


async def _issue_receipt(
    db: AsyncSession,
    payment: Payment,
    *,
    actor_id: UUID,
) -> Receipt:
    fy = await get_financial_year_in_society(
        db, payment.financial_year_id, payment.society_id
    )
    receipt_number = await next_receipt_number(db, fy)
    receipt = Receipt(
        society_id=payment.society_id,
        payment_id=payment.id,
        resident_id=payment.resident_id,
        financial_year_id=payment.financial_year_id,
        receipt_number=receipt_number,
        issued_at=utcnow(),
        issued_by=actor_id,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        is_void=False,
        metadata_json={
            "mode": payment.mode,
            "paymentNumber": payment.payment_number,
            "payerName": payment.payer_name,
        },
        is_active=True,
        version=1,
    )
    apply_create_audit(receipt, actor_id)
    db.add(receipt)
    await db.flush()
    publish_simple(
        "ReceiptGenerated",
        society_id=payment.society_id,
        entity_type="receipt",
        entity_id=receipt.id,
        actor_id=actor_id,
        payload={
            "receiptId": str(receipt.id),
            "receiptNumber": receipt.receipt_number,
            "paymentId": str(payment.id),
        },
    )
    return receipt


async def create_payment(
    db: AsyncSession,
    body: PaymentCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    if body.idempotencyKey:
        existing = (
            await db.execute(
                select(Payment).where(
                    Payment.society_id == society_id,
                    Payment.idempotency_key == body.idempotencyKey,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return await get_payment(db, existing.id, actor_society_id=society_id)

    resident = (
        await db.execute(
            select(Resident).where(
                Resident.id == body.residentId,
                Resident.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")

    fy = await get_financial_year_in_society(db, body.financialYearId, society_id)
    assert_fy_open(fy)
    period = None
    if body.accountingPeriodId:
        period = await get_period_in_society(db, body.accountingPeriodId, society_id)
        assert_period_open(period)

    status = "cleared" if body.mode in IMMEDIATE_CLEAR_MODES else "pending"
    payment_number = await next_payment_number(db, fy)
    payment = Payment(
        society_id=society_id,
        resident_id=resident.id,
        occupancy_id=body.occupancyId,
        collected_by=actor_id,
        collected_by_staff_id=body.collectedByStaffId,
        financial_year_id=fy.id,
        accounting_period_id=period.id if period else None,
        payment_number=payment_number,
        amount_minor=body.amountMinor,
        unallocated_minor=body.amountMinor,
        currency=body.currency,
        mode=body.mode,
        status=status,
        payment_date=body.paymentDate or utcnow(),
        value_date=body.valueDate,
        external_reference=body.externalReference,
        cheque_number=body.chequeNumber,
        bank_name=body.bankName,
        upi_vpa=body.upiVpa,
        gateway_provider=body.gatewayProvider,
        gateway_txn_id=body.gatewayTxnId,
        idempotency_key=body.idempotencyKey,
        payer_name=body.payerName or resident.name,
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(payment, actor_id)
    db.add(payment)
    await db.flush()

    if body.allocations:
        await _create_allocations(
            db,
            payment,
            body.allocations,
            actor_id=actor_id,
            society_id=society_id,
            apply_to_bills=status == "cleared",
        )
    elif body.autoAllocate and status == "cleared":
        await _auto_allocate_fifo(
            db, payment, actor_id=actor_id, society_id=society_id
        )

    receipt = None
    if status == "cleared":
        publish_simple(
            "PaymentReceived",
            society_id=society_id,
            entity_type="payment",
            entity_id=payment.id,
            actor_id=actor_id,
            payload={
                "paymentId": str(payment.id),
                "amountMinor": payment.amount_minor,
                "mode": payment.mode,
            },
        )
        receipt = await _issue_receipt(db, payment, actor_id=actor_id)

    await db.commit()
    data = await get_payment(db, payment.id, actor_society_id=society_id)
    if receipt:
        data["receipt"] = _receipt_dict(receipt, resident_name=resident.name)
    return data


async def allocate_payment(
    db: AsyncSession,
    payment_id: UUID,
    body: PaymentAllocateRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    payment = await _get_payment(db, payment_id, society_id)
    if payment.status != "cleared":
        raise ApiError(422, "Only cleared payments can be allocated")
    await _create_allocations(
        db,
        payment,
        body.allocations,
        actor_id=actor_id,
        society_id=society_id,
        apply_to_bills=True,
    )
    apply_update_audit(payment, actor_id)
    await db.commit()
    return await get_payment(db, payment.id, actor_society_id=society_id)


async def reverse_payment(
    db: AsyncSession,
    payment_id: UUID,
    body: StatusNotesBody | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    payment = await _get_payment(db, payment_id, society_id)
    if payment.status != "cleared":
        raise ApiError(422, "Only cleared payments can be reversed")

    allocations = (
        await db.execute(
            select(PaymentAllocation).where(
                PaymentAllocation.payment_id == payment.id,
                PaymentAllocation.is_active.is_(True),
                PaymentAllocation.allocation_type == "bill",
            )
        )
    ).scalars().all()
    for alloc in allocations:
        if not alloc.bill_id:
            continue
        bill = await get_bill_in_society(db, alloc.bill_id, society_id)
        bill.paid_minor = max(0, bill.paid_minor - alloc.amount_minor)
        bill.outstanding_minor = max(0, bill.net_minor - bill.paid_minor)
        update_bill_status_from_amounts(bill)
        apply_update_audit(bill, actor_id)
        alloc.is_active = False
        apply_update_audit(alloc, actor_id)

    payment.status = "reversed"
    if body and body.notes:
        payment.notes = body.notes
    apply_update_audit(payment, actor_id)

    receipt = (
        await db.execute(
            select(Receipt).where(
                Receipt.payment_id == payment.id,
                Receipt.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if receipt:
        receipt.is_void = True
        apply_update_audit(receipt, actor_id)

    await db.commit()
    publish_simple(
        "PaymentReversed",
        society_id=society_id,
        entity_type="payment",
        entity_id=payment.id,
        actor_id=actor_id,
        payload={
            "paymentId": str(payment.id),
            "originalPaymentId": str(payment.id),
        },
    )
    return await get_payment(db, payment.id, actor_society_id=society_id)


async def list_payments(
    db: AsyncSession,
    query: PaymentListQueryParams,
    *,
    actor_society_id: UUID | None,
    resident_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    rid = resident_id or query.resident_id
    builder = (
        ListQueryBuilder(Payment)
        .filter_eq("society_id", society_id)
        .search(query.search, "payment_number", "external_reference", "payer_name")
        .filter_eq("status", query.status)
        .filter_eq("mode", query.mode)
        .filter_eq("resident_id", rid)
        .filter_eq("occupancy_id", query.occupancy_id)
        .filter_eq("financial_year_id", query.financial_year_id)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("payment_date", "created_at", "amount_minor", "status", "mode", "payment_number"),
            default="payment_date",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    names = await _resident_names(db, {p.resident_id for p in items})
    return {
        "payments": [
            _payment_dict(p, resident_name=names.get(p.resident_id)) for p in items
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_payment(
    db: AsyncSession, payment_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    payment = await _get_payment(db, payment_id, society_id)
    names = await _resident_names(db, {payment.resident_id})
    allocs = await _load_allocations(db, [payment.id])
    return {
        "payment": _payment_dict(
            payment,
            resident_name=names.get(payment.resident_id),
            allocations=allocs.get(payment.id, []),
        )
    }


async def list_receipts(
    db: AsyncSession,
    query: ReceiptListQueryParams,
    *,
    actor_society_id: UUID | None,
    resident_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    rid = resident_id or query.resident_id
    builder = (
        ListQueryBuilder(Receipt)
        .filter_eq("society_id", society_id)
        .search(query.search, "receipt_number")
        .filter_eq("resident_id", rid)
        .filter_eq("payment_id", query.payment_id)
        .filter_eq("financial_year_id", query.financial_year_id)
        .filter_eq("is_void", query.is_void)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("issued_at", "created_at", "amount_minor", "receipt_number"),
            default="issued_at",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    names = await _resident_names(db, {r.resident_id for r in items})
    return {
        "receipts": [
            _receipt_dict(r, resident_name=names.get(r.resident_id)) for r in items
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_receipt(
    db: AsyncSession, receipt_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    receipt = await _get_receipt(db, receipt_id, society_id)
    names = await _resident_names(db, {receipt.resident_id})
    return {
        "receipt": _receipt_dict(receipt, resident_name=names.get(receipt.resident_id))
    }


async def get_resident_outstanding(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    from Services.billing_helpers import resolve_resident_for_user, sum_resident_outstanding

    society_id = require_society_id(actor_society_id)
    resident, _ = await resolve_resident_for_user(
        db, actor_id=actor_id, society_id=society_id
    )
    total = await sum_resident_outstanding(
        db, society_id=society_id, resident_id=resident.id
    )
    bills = (
        await db.execute(
            select(MaintenanceBill).where(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.status.in_(("published", "partially_paid", "overdue")),
                MaintenanceBill.outstanding_minor > 0,
                MaintenanceBill.is_active.is_(True),
            ).order_by(MaintenanceBill.due_date.asc())
        )
    ).scalars().all()
    return {
        "residentId": str(resident.id),
        "outstandingMinor": total,
        "billCount": len(bills),
        "bills": [
            {
                "id": str(b.id),
                "billNumber": b.bill_number,
                "dueDate": b.due_date.isoformat(),
                "outstandingMinor": b.outstanding_minor,
                "status": b.status,
            }
            for b in bills
        ],
    }
