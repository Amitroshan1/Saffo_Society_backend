"""Resident billing portal routes — /api/v1/resident/bills|payments|receipts|outstanding."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.billing_list_query import (
    get_bill_list_query,
    get_payment_list_query,
    get_receipt_list_query,
)
from Schemas.billing import BillListQueryParams, PaymentListQueryParams, ReceiptListQueryParams
from Services import resident_billing_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-billing"])


@router.get("/resident/bills")
async def resident_list_bills(
    query: BillListQueryParams = Depends(get_bill_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.list_bills(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident bills fetched", data)


@router.get("/resident/bills/{bill_id}")
async def resident_get_bill(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.get_bill(
        db, bill_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident bill fetched", data)


@router.get("/resident/payments")
async def resident_list_payments(
    query: PaymentListQueryParams = Depends(get_payment_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.list_payments(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident payments fetched", data)


@router.get("/resident/receipts")
async def resident_list_receipts(
    query: ReceiptListQueryParams = Depends(get_receipt_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.list_receipts(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident receipts fetched", data)


@router.get("/resident/receipts/{receipt_id}")
async def resident_get_receipt(
    receipt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.get_receipt(
        db, receipt_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident receipt fetched", data)


@router.get("/resident/outstanding")
async def resident_outstanding(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_billing_service.get_outstanding(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident outstanding fetched", data)
