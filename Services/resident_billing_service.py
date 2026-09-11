"""Resident billing portal — scopes shared billing/payment services to the caller."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.billing import BillListQueryParams, PaymentListQueryParams, ReceiptListQueryParams
from Services import bill_service, payment_service
from Services.billing_helpers import get_bill_in_society, resolve_resident_for_user
from Utils.errors import ApiError


async def list_bills(
    db: AsyncSession,
    query: BillListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, _ = await resolve_resident_for_user(db, actor_id=actor_id, society_id=actor_society_id)
    return await bill_service.list_bills(
        db, query, actor_society_id=actor_society_id, resident_id=resident.id
    )


async def get_bill(
    db: AsyncSession,
    bill_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, _ = await resolve_resident_for_user(db, actor_id=actor_id, society_id=actor_society_id)
    bill = await get_bill_in_society(db, bill_id, actor_society_id)
    if bill.resident_id != resident.id:
        raise ApiError(404, "Bill not found")
    return await bill_service.get_bill(db, bill_id, actor_society_id=actor_society_id)


async def list_payments(
    db: AsyncSession,
    query: PaymentListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, _ = await resolve_resident_for_user(db, actor_id=actor_id, society_id=actor_society_id)
    return await payment_service.list_payments(
        db, query, actor_society_id=actor_society_id, resident_id=resident.id
    )


async def list_receipts(
    db: AsyncSession,
    query: ReceiptListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, _ = await resolve_resident_for_user(db, actor_id=actor_id, society_id=actor_society_id)
    return await payment_service.list_receipts(
        db, query, actor_society_id=actor_society_id, resident_id=resident.id
    )


async def get_receipt(
    db: AsyncSession,
    receipt_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, _ = await resolve_resident_for_user(db, actor_id=actor_id, society_id=actor_society_id)
    data = await payment_service.get_receipt(db, receipt_id, actor_society_id=actor_society_id)
    if data["receipt"]["residentId"] != str(resident.id):
        raise ApiError(404, "Receipt not found")
    return data


async def get_outstanding(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await payment_service.get_resident_outstanding(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
