"""Billing list query dependencies."""

from uuid import UUID

from fastapi import Query

from Schemas.billing import (
    AccountingPeriodListQueryParams,
    BillListQueryParams,
    BillingCycleListQueryParams,
    ChargeHeadListQueryParams,
    DiscountRuleListQueryParams,
    FinancialYearListQueryParams,
    LateFeeRuleListQueryParams,
    PaymentListQueryParams,
    ReceiptListQueryParams,
)


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_charge_head_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("display_order", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    category: str | None = Query(None),
) -> ChargeHeadListQueryParams:
    return ChargeHeadListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        category=_norm_enum(category),
    )


def get_billing_cycle_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    frequency: str | None = Query(None),
) -> BillingCycleListQueryParams:
    return BillingCycleListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        frequency=_norm_enum(frequency),
    )


def get_financial_year_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("start_date", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
) -> FinancialYearListQueryParams:
    return FinancialYearListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
    )


def get_accounting_period_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("start_date", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    financial_year_id: UUID | None = Query(None, alias="financialYearId"),
    status: str | None = Query(None),
) -> AccountingPeriodListQueryParams:
    return AccountingPeriodListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        financial_year_id=financial_year_id,
        status=_norm_enum(status),
    )


def get_late_fee_rule_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("priority", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
) -> LateFeeRuleListQueryParams:
    return LateFeeRuleListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
    )


def get_discount_rule_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
) -> DiscountRuleListQueryParams:
    return DiscountRuleListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
    )


def get_bill_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    occupancy_id: UUID | None = Query(None, alias="occupancyId"),
    resident_id: UUID | None = Query(None, alias="residentId"),
    flat_id: UUID | None = Query(None, alias="flatId"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    wing_id: UUID | None = Query(None, alias="wingId"),
    billing_cycle_id: UUID | None = Query(None, alias="billingCycleId"),
    financial_year_id: UUID | None = Query(None, alias="financialYearId"),
) -> BillListQueryParams:
    return BillListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        occupancy_id=occupancy_id,
        resident_id=resident_id,
        flat_id=flat_id,
        building_id=building_id,
        wing_id=wing_id,
        billing_cycle_id=billing_cycle_id,
        financial_year_id=financial_year_id,
    )


def get_payment_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("payment_date", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    mode: str | None = Query(None),
    resident_id: UUID | None = Query(None, alias="residentId"),
    occupancy_id: UUID | None = Query(None, alias="occupancyId"),
    financial_year_id: UUID | None = Query(None, alias="financialYearId"),
) -> PaymentListQueryParams:
    return PaymentListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        mode=_norm_enum(mode),
        resident_id=resident_id,
        occupancy_id=occupancy_id,
        financial_year_id=financial_year_id,
    )


def get_receipt_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("issued_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    resident_id: UUID | None = Query(None, alias="residentId"),
    payment_id: UUID | None = Query(None, alias="paymentId"),
    financial_year_id: UUID | None = Query(None, alias="financialYearId"),
    is_void: bool | None = Query(None, alias="isVoid"),
) -> ReceiptListQueryParams:
    return ReceiptListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        resident_id=resident_id,
        payment_id=payment_id,
        financial_year_id=financial_year_id,
        is_void=is_void,
    )
