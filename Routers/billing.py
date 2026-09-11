"""Billing & Accounting routes — /api/v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.billing_list_query import (
    get_accounting_period_list_query,
    get_bill_list_query,
    get_billing_cycle_list_query,
    get_charge_head_list_query,
    get_discount_rule_list_query,
    get_financial_year_list_query,
    get_late_fee_rule_list_query,
    get_payment_list_query,
    get_receipt_list_query,
)
from Schemas.billing import (
    AccountingPeriodCreate,
    AccountingPeriodListQueryParams,
    ApplyDiscountRequest,
    BillGenerateRequest,
    BillListQueryParams,
    BillingCycleCreate,
    BillingCycleListQueryParams,
    BillingCycleUpdate,
    ChargeHeadCreate,
    ChargeHeadListQueryParams,
    ChargeHeadUpdate,
    DiscountRuleCreate,
    DiscountRuleListQueryParams,
    DiscountRuleUpdate,
    FinancialYearCreate,
    FinancialYearListQueryParams,
    FinancialYearUpdate,
    LateFeeRuleCreate,
    LateFeeRuleListQueryParams,
    LateFeeRuleUpdate,
    MaintenanceBillCreate,
    MaintenanceBillUpdate,
    PaymentAllocateRequest,
    PaymentCreate,
    PaymentListQueryParams,
    ReceiptListQueryParams,
    StatusNotesBody,
    WriteOffRequest,
)
from Services import (
    bill_service,
    billing_cycle_service,
    billing_dashboard_service,
    billing_report_service,
    charge_head_service,
    discount_rule_service,
    financial_year_service,
    late_fee_rule_service,
    payment_service,
)
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["billing"])
FINANCE_ROLES = ("admin", "finance")


# ---------------------------------------------------------------------------
# Charge heads
# ---------------------------------------------------------------------------


@router.post("/charge-heads")
async def create_charge_head(
    body: ChargeHeadCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.create_charge_head(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Charge head created successfully", data)


@router.get("/charge-heads")
async def list_charge_heads(
    query: ChargeHeadListQueryParams = Depends(get_charge_head_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.list_charge_heads(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Charge heads fetched", data)


@router.get("/charge-heads/{entity_id}")
async def get_charge_head(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.get_charge_head(
        db, entity_id, actor_society_id=current.society_id
    )
    return success_response(200, "Charge head fetched", data)


@router.patch("/charge-heads/{entity_id}")
async def update_charge_head(
    entity_id: UUID,
    body: ChargeHeadUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.update_charge_head(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Charge head updated successfully", data)


@router.post("/charge-heads/{entity_id}/deactivate")
async def deactivate_charge_head(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.set_charge_head_active(
        db,
        entity_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Charge head deactivated"), data)


@router.post("/charge-heads/{entity_id}/activate")
async def activate_charge_head(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await charge_head_service.set_charge_head_active(
        db,
        entity_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Charge head activated"), data)


# ---------------------------------------------------------------------------
# Billing cycles
# ---------------------------------------------------------------------------


@router.post("/billing-cycles")
async def create_billing_cycle(
    body: BillingCycleCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.create_billing_cycle(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Billing cycle created successfully", data)


@router.get("/billing-cycles")
async def list_billing_cycles(
    query: BillingCycleListQueryParams = Depends(get_billing_cycle_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.list_billing_cycles(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Billing cycles fetched", data)


@router.get("/billing-cycles/{entity_id}")
async def get_billing_cycle(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.get_billing_cycle(
        db, entity_id, actor_society_id=current.society_id
    )
    return success_response(200, "Billing cycle fetched", data)


@router.patch("/billing-cycles/{entity_id}")
async def update_billing_cycle(
    entity_id: UUID,
    body: BillingCycleUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.update_billing_cycle(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Billing cycle updated successfully", data)


@router.post("/billing-cycles/{entity_id}/deactivate")
async def deactivate_billing_cycle(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.set_billing_cycle_active(
        db,
        entity_id,
        active=False,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Billing cycle deactivated"), data)


@router.post("/billing-cycles/{entity_id}/activate")
async def activate_billing_cycle(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_cycle_service.set_billing_cycle_active(
        db,
        entity_id,
        active=True,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, data.pop("message", "Billing cycle activated"), data)


# ---------------------------------------------------------------------------
# Late fee & discount rules
# ---------------------------------------------------------------------------


@router.post("/late-fee-rules")
async def create_late_fee_rule(
    body: LateFeeRuleCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await late_fee_rule_service.create_late_fee_rule(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Late fee rule created successfully", data)


@router.get("/late-fee-rules")
async def list_late_fee_rules(
    query: LateFeeRuleListQueryParams = Depends(get_late_fee_rule_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await late_fee_rule_service.list_late_fee_rules(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Late fee rules fetched", data)


@router.get("/late-fee-rules/{entity_id}")
async def get_late_fee_rule(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await late_fee_rule_service.get_late_fee_rule(
        db, entity_id, actor_society_id=current.society_id
    )
    return success_response(200, "Late fee rule fetched", data)


@router.patch("/late-fee-rules/{entity_id}")
async def update_late_fee_rule(
    entity_id: UUID,
    body: LateFeeRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await late_fee_rule_service.update_late_fee_rule(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Late fee rule updated successfully", data)


@router.delete("/late-fee-rules/{entity_id}")
async def delete_late_fee_rule(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await late_fee_rule_service.delete_late_fee_rule(
        db, entity_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Late fee rule deactivated"), data)


@router.post("/discount-rules")
async def create_discount_rule(
    body: DiscountRuleCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await discount_rule_service.create_discount_rule(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Discount rule created successfully", data)


@router.get("/discount-rules")
async def list_discount_rules(
    query: DiscountRuleListQueryParams = Depends(get_discount_rule_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await discount_rule_service.list_discount_rules(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Discount rules fetched", data)


@router.get("/discount-rules/{entity_id}")
async def get_discount_rule(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await discount_rule_service.get_discount_rule(
        db, entity_id, actor_society_id=current.society_id
    )
    return success_response(200, "Discount rule fetched", data)


@router.patch("/discount-rules/{entity_id}")
async def update_discount_rule(
    entity_id: UUID,
    body: DiscountRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await discount_rule_service.update_discount_rule(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Discount rule updated successfully", data)


@router.delete("/discount-rules/{entity_id}")
async def delete_discount_rule(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await discount_rule_service.delete_discount_rule(
        db, entity_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, data.pop("message", "Discount rule deactivated"), data)


# ---------------------------------------------------------------------------
# Financial years & periods
# ---------------------------------------------------------------------------


@router.post("/financial-years")
async def create_financial_year(
    body: FinancialYearCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.create_financial_year(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Financial year created successfully", data)


@router.get("/financial-years")
async def list_financial_years(
    query: FinancialYearListQueryParams = Depends(get_financial_year_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.list_financial_years(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Financial years fetched", data)


@router.get("/financial-years/{entity_id}")
async def get_financial_year(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.get_financial_year(
        db, entity_id, actor_society_id=current.society_id
    )
    return success_response(200, "Financial year fetched", data)


@router.patch("/financial-years/{entity_id}")
async def update_financial_year(
    entity_id: UUID,
    body: FinancialYearUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.update_financial_year(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Financial year updated successfully", data)


@router.post("/financial-years/{entity_id}/close")
async def close_financial_year(
    entity_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await financial_year_service.close_financial_year(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Financial year closed", data)


@router.post("/accounting-periods")
async def create_accounting_period(
    body: AccountingPeriodCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.create_accounting_period(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Accounting period created successfully", data)


@router.get("/accounting-periods")
async def list_accounting_periods(
    query: AccountingPeriodListQueryParams = Depends(get_accounting_period_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.list_accounting_periods(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Accounting periods fetched", data)


@router.post("/accounting-periods/{entity_id}/close")
async def close_accounting_period(
    entity_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await financial_year_service.close_accounting_period(
        db, entity_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Accounting period closed", data)


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------


@router.post("/bills")
async def create_bill(
    body: MaintenanceBillCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.create_bill(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Bill created successfully", data)


@router.get("/bills")
async def list_bills(
    query: BillListQueryParams = Depends(get_bill_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.list_bills(db, query, actor_society_id=current.society_id)
    return success_response(200, "Bills fetched", data)


@router.post("/bills/generate")
async def generate_bills(
    body: BillGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.generate_bills(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Bills generated", data)


@router.get("/bills/{bill_id}")
async def get_bill(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.get_bill(db, bill_id, actor_society_id=current.society_id)
    return success_response(200, "Bill fetched", data)


@router.patch("/bills/{bill_id}")
async def update_bill(
    bill_id: UUID,
    body: MaintenanceBillUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.update_draft_bill(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Bill updated successfully", data)


@router.post("/bills/{bill_id}/publish")
async def publish_bill(
    bill_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.publish_bill(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Bill published", data)


@router.post("/bills/{bill_id}/cancel")
async def cancel_bill(
    bill_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.cancel_bill(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Bill cancelled", data)


@router.post("/bills/{bill_id}/write-off")
async def write_off_bill(
    bill_id: UUID,
    body: WriteOffRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.write_off_bill(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Bill written off", data)


@router.post("/bills/{bill_id}/apply-late-fee")
async def apply_late_fee(
    bill_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.apply_late_fee(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Late fee applied", data)


@router.post("/bills/{bill_id}/apply-discount")
async def apply_discount(
    bill_id: UUID,
    body: ApplyDiscountRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await bill_service.apply_discount(
        db, bill_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Discount applied", data)


# ---------------------------------------------------------------------------
# Payments & receipts
# ---------------------------------------------------------------------------


@router.post("/payments")
async def create_payment(
    body: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.create_payment(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Payment recorded successfully", data)


@router.get("/payments")
async def list_payments(
    query: PaymentListQueryParams = Depends(get_payment_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.list_payments(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Payments fetched", data)


@router.get("/payments/{payment_id}")
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.get_payment(
        db, payment_id, actor_society_id=current.society_id
    )
    return success_response(200, "Payment fetched", data)


@router.post("/payments/{payment_id}/allocate")
async def allocate_payment(
    payment_id: UUID,
    body: PaymentAllocateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.allocate_payment(
        db, payment_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Payment allocated", data)


@router.post("/payments/{payment_id}/reverse")
async def reverse_payment(
    payment_id: UUID,
    body: StatusNotesBody | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.reverse_payment(
        db, payment_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Payment reversed", data)


@router.get("/receipts")
async def list_receipts(
    query: ReceiptListQueryParams = Depends(get_receipt_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.list_receipts(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Receipts fetched", data)


@router.get("/receipts/{receipt_id}")
async def get_receipt(
    receipt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await payment_service.get_receipt(
        db, receipt_id, actor_society_id=current.society_id
    )
    return success_response(200, "Receipt fetched", data)


# ---------------------------------------------------------------------------
# Dashboard & reports
# ---------------------------------------------------------------------------


@router.get("/billing/dashboard")
async def billing_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await billing_dashboard_service.get_dashboard(
        db, actor_society_id=current.society_id
    )
    return success_response(200, "Billing dashboard fetched", data)


@router.get("/billing/reports/{report_key}")
async def billing_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
    as_of: str | None = Query(None, alias="asOf"),
    building_id: str | None = Query(None, alias="buildingId"),
    wing_id: str | None = Query(None, alias="wingId"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    mode: str | None = Query(None),
    financial_year_id: str | None = Query(None, alias="financialYearId"),
    fy: str | None = Query(None),
    period_id: str | None = Query(None, alias="periodId"),
    period: str | None = Query(None),
    min_outstanding: str | None = Query(None, alias="minOutstanding"),
    days_overdue: str | None = Query(None, alias="daysOverdue"),
    resident_id: str | None = Query(None, alias="residentId"),
    occupancy_id: str | None = Query(None, alias="occupancyId"),
    year: str | None = Query(None),
    granularity: str | None = Query(None),
):
    data = await billing_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={
            "asOf": as_of,
            "buildingId": building_id,
            "wingId": wing_id,
            "from": from_date,
            "to": to_date,
            "mode": mode,
            "financialYearId": financial_year_id,
            "fy": fy,
            "periodId": period_id,
            "period": period,
            "minOutstanding": min_outstanding,
            "daysOverdue": days_overdue,
            "residentId": resident_id,
            "occupancyId": occupancy_id,
            "year": year,
            "granularity": granularity,
        },
    )
    return success_response(200, "Billing report fetched", data)
