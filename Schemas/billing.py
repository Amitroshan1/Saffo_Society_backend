"""Pydantic schemas for Billing & Accounting module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from Schemas.common import ListQueryParams

CHARGE_CATEGORY_VALUES = (
    "maintenance",
    "water",
    "parking",
    "security",
    "lift",
    "sinking_fund",
    "repair_fund",
    "club_house",
    "electricity",
    "property_tax",
    "other",
)
BILLING_FREQUENCY_VALUES = (
    "monthly",
    "quarterly",
    "half_yearly",
    "yearly",
    "manual",
    "custom",
)
BILL_STATUS_VALUES = (
    "draft",
    "generated",
    "published",
    "partially_paid",
    "paid",
    "overdue",
    "cancelled",
    "write_off",
)
PAYMENT_MODE_VALUES = (
    "cash",
    "cheque",
    "upi",
    "bank_transfer",
    "card",
    "online_gateway",
)
PAYMENT_STATUS_VALUES = ("pending", "cleared", "failed", "reversed")
FEE_TYPE_VALUES = ("fixed", "percentage", "daily")
DISCOUNT_TYPE_VALUES = ("fixed", "percentage")
ALLOCATION_TYPE_VALUES = ("bill", "advance", "on_account")
FY_STATUS_VALUES = ("open", "closing", "closed")
PERIOD_STATUS_VALUES = ("open", "closed")
DISCOUNT_SCOPE_VALUES = ("society", "resident", "occupancy", "bill")
LATE_FEE_APPLY_ON_VALUES = ("outstanding", "bill_net")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_enum(value: str, allowed: tuple[str, ...], label: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
    return normalized


def _normalize_code(value: str) -> str:
    value = value.strip().upper()
    if not value:
        raise ValueError("code cannot be blank")
    return value


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


class ChargeHeadListQueryParams(ListQueryParams):
    category: Optional[str] = None
    model_config = {"populate_by_name": True}


class BillingCycleListQueryParams(ListQueryParams):
    frequency: Optional[str] = None
    model_config = {"populate_by_name": True}


class FinancialYearListQueryParams(ListQueryParams):
    status: Optional[str] = None
    model_config = {"populate_by_name": True}


class AccountingPeriodListQueryParams(ListQueryParams):
    financial_year_id: Optional[UUID] = Field(None, alias="financialYearId")
    status: Optional[str] = None
    model_config = {"populate_by_name": True}


class LateFeeRuleListQueryParams(ListQueryParams):
    model_config = {"populate_by_name": True}


class DiscountRuleListQueryParams(ListQueryParams):
    model_config = {"populate_by_name": True}


class BillListQueryParams(ListQueryParams):
    status: Optional[str] = None
    occupancy_id: Optional[UUID] = Field(None, alias="occupancyId")
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    flat_id: Optional[UUID] = Field(None, alias="flatId")
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    wing_id: Optional[UUID] = Field(None, alias="wingId")
    billing_cycle_id: Optional[UUID] = Field(None, alias="billingCycleId")
    financial_year_id: Optional[UUID] = Field(None, alias="financialYearId")
    model_config = {"populate_by_name": True}


class PaymentListQueryParams(ListQueryParams):
    status: Optional[str] = None
    mode: Optional[str] = None
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    occupancy_id: Optional[UUID] = Field(None, alias="occupancyId")
    financial_year_id: Optional[UUID] = Field(None, alias="financialYearId")
    model_config = {"populate_by_name": True}


class ReceiptListQueryParams(ListQueryParams):
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    payment_id: Optional[UUID] = Field(None, alias="paymentId")
    financial_year_id: Optional[UUID] = Field(None, alias="financialYearId")
    is_void: Optional[bool] = Field(None, alias="isVoid")
    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Charge head
# ---------------------------------------------------------------------------


class ChargeHeadCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., max_length=64)
    defaultAmountMinor: int = Field(0, ge=0)
    isRecurring: bool = False
    isTaxable: bool = False
    glCode: Optional[str] = Field(None, max_length=64)
    displayOrder: int = Field(0, ge=0)
    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return _normalize_code(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return _normalize_enum(value, CHARGE_CATEGORY_VALUES, "category")

    @field_validator("glCode", "description", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ChargeHeadUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    defaultAmountMinor: Optional[int] = Field(None, ge=0)
    isRecurring: Optional[bool] = None
    isTaxable: Optional[bool] = None
    glCode: Optional[str] = Field(None, max_length=64)
    displayOrder: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name", "glCode", "description", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, CHARGE_CATEGORY_VALUES, "category")


class ChargeHeadOut(BaseModel):
    id: UUID
    societyId: UUID
    code: str
    name: str
    category: str
    defaultAmountMinor: int
    isRecurring: bool
    isTaxable: bool
    glCode: Optional[str] = None
    displayOrder: int
    description: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "ChargeHeadOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            code=row.code,
            name=row.name,
            category=row.category,
            defaultAmountMinor=row.default_amount_minor,
            isRecurring=row.is_recurring,
            isTaxable=row.is_taxable,
            glCode=row.gl_code,
            displayOrder=row.display_order,
            description=row.description,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


# ---------------------------------------------------------------------------
# Billing cycle
# ---------------------------------------------------------------------------


class BillingCycleCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    frequency: str = Field(..., max_length=32)
    dayOfMonth: Optional[int] = Field(None, ge=1, le=28)
    customCron: Optional[str] = Field(None, max_length=128)
    periodLabelTemplate: Optional[str] = Field(None, max_length=128)
    defaultDueDays: int = Field(10, ge=0)
    autoPublish: bool = False
    nextRunAt: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return _normalize_code(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str) -> str:
        return _normalize_enum(value, BILLING_FREQUENCY_VALUES, "frequency")

    @field_validator("customCron", "periodLabelTemplate", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BillingCycleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    frequency: Optional[str] = Field(None, max_length=32)
    dayOfMonth: Optional[int] = Field(None, ge=1, le=28)
    customCron: Optional[str] = Field(None, max_length=128)
    periodLabelTemplate: Optional[str] = Field(None, max_length=128)
    defaultDueDays: Optional[int] = Field(None, ge=0)
    autoPublish: Optional[bool] = None
    nextRunAt: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name", "customCron", "periodLabelTemplate", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, BILLING_FREQUENCY_VALUES, "frequency")


class BillingCycleOut(BaseModel):
    id: UUID
    societyId: UUID
    code: str
    name: str
    frequency: str
    dayOfMonth: Optional[int] = None
    customCron: Optional[str] = None
    periodLabelTemplate: Optional[str] = None
    defaultDueDays: int
    autoPublish: bool
    nextRunAt: Optional[datetime] = None
    lastRunAt: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "BillingCycleOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            code=row.code,
            name=row.name,
            frequency=row.frequency,
            dayOfMonth=row.day_of_month,
            customCron=row.custom_cron,
            periodLabelTemplate=row.period_label_template,
            defaultDueDays=row.default_due_days,
            autoPublish=row.auto_publish,
            nextRunAt=row.next_run_at,
            lastRunAt=row.last_run_at,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


# ---------------------------------------------------------------------------
# Financial year & accounting period
# ---------------------------------------------------------------------------


class FinancialYearCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    startDate: date
    endDate: date
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return _normalize_code(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "FinancialYearCreate":
        if self.endDate < self.startDate:
            raise ValueError("endDate must be on or after startDate")
        return self


class FinancialYearUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class FinancialYearOut(BaseModel):
    id: UUID
    societyId: UUID
    code: str
    name: str
    startDate: date
    endDate: date
    status: str
    nextBillSeq: int
    nextReceiptSeq: int
    closedAt: Optional[datetime] = None
    closedBy: Optional[UUID] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "FinancialYearOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            code=row.code,
            name=row.name,
            startDate=row.start_date,
            endDate=row.end_date,
            status=row.status,
            nextBillSeq=row.next_bill_seq,
            nextReceiptSeq=row.next_receipt_seq,
            closedAt=row.closed_at,
            closedBy=row.closed_by,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class AccountingPeriodCreate(BaseModel):
    financialYearId: UUID
    periodKey: str = Field(..., min_length=1, max_length=32)
    startDate: date
    endDate: date
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("periodKey")
    @classmethod
    def validate_period_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("periodKey cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "AccountingPeriodCreate":
        if self.endDate < self.startDate:
            raise ValueError("endDate must be on or after startDate")
        return self


class AccountingPeriodOut(BaseModel):
    id: UUID
    societyId: UUID
    financialYearId: UUID
    periodKey: str
    startDate: date
    endDate: date
    status: str
    closedAt: Optional[datetime] = None
    closedBy: Optional[UUID] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "AccountingPeriodOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            financialYearId=row.financial_year_id,
            periodKey=row.period_key,
            startDate=row.start_date,
            endDate=row.end_date,
            status=row.status,
            closedAt=row.closed_at,
            closedBy=row.closed_by,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class StatusNotesBody(BaseModel):
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Late fee & discount rules
# ---------------------------------------------------------------------------


class LateFeeRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    feeType: str = Field(..., max_length=32)
    graceDays: int = Field(0, ge=0)
    fixedAmountMinor: Optional[int] = Field(None, ge=0)
    percentageBps: Optional[int] = Field(None, ge=0)
    dailyAmountMinor: Optional[int] = Field(None, ge=0)
    maxPenaltyMinor: Optional[int] = Field(None, ge=0)
    applyOn: str = Field(default="outstanding", max_length=32)
    priority: int = Field(0, ge=0)
    chargeHeadId: Optional[UUID] = None
    billingCycleId: Optional[UUID] = None
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("feeType")
    @classmethod
    def validate_fee_type(cls, value: str) -> str:
        return _normalize_enum(value, FEE_TYPE_VALUES, "feeType")

    @field_validator("applyOn")
    @classmethod
    def validate_apply_on(cls, value: str) -> str:
        return _normalize_enum(value, LATE_FEE_APPLY_ON_VALUES, "applyOn")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_fee_fields(self) -> "LateFeeRuleCreate":
        if self.feeType == "fixed" and self.fixedAmountMinor is None:
            raise ValueError("fixedAmountMinor is required for fixed feeType")
        if self.feeType == "percentage" and self.percentageBps is None:
            raise ValueError("percentageBps is required for percentage feeType")
        if self.feeType == "daily" and self.dailyAmountMinor is None:
            raise ValueError("dailyAmountMinor is required for daily feeType")
        return self


class LateFeeRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    feeType: Optional[str] = Field(None, max_length=32)
    graceDays: Optional[int] = Field(None, ge=0)
    fixedAmountMinor: Optional[int] = Field(None, ge=0)
    percentageBps: Optional[int] = Field(None, ge=0)
    dailyAmountMinor: Optional[int] = Field(None, ge=0)
    maxPenaltyMinor: Optional[int] = Field(None, ge=0)
    applyOn: Optional[str] = Field(None, max_length=32)
    priority: Optional[int] = Field(None, ge=0)
    chargeHeadId: Optional[UUID] = None
    billingCycleId: Optional[UUID] = None
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("feeType")
    @classmethod
    def validate_fee_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, FEE_TYPE_VALUES, "feeType")

    @field_validator("applyOn")
    @classmethod
    def validate_apply_on(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, LATE_FEE_APPLY_ON_VALUES, "applyOn")


class LateFeeRuleOut(BaseModel):
    id: UUID
    societyId: UUID
    chargeHeadId: Optional[UUID] = None
    billingCycleId: Optional[UUID] = None
    name: str
    graceDays: int
    feeType: str
    fixedAmountMinor: Optional[int] = None
    percentageBps: Optional[int] = None
    dailyAmountMinor: Optional[int] = None
    maxPenaltyMinor: Optional[int] = None
    applyOn: str
    priority: int
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "LateFeeRuleOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            chargeHeadId=row.charge_head_id,
            billingCycleId=row.billing_cycle_id,
            name=row.name,
            graceDays=row.grace_days,
            feeType=row.fee_type,
            fixedAmountMinor=row.fixed_amount_minor,
            percentageBps=row.percentage_bps,
            dailyAmountMinor=row.daily_amount_minor,
            maxPenaltyMinor=row.max_penalty_minor,
            applyOn=row.apply_on,
            priority=row.priority,
            effectiveFrom=row.effective_from,
            effectiveTo=row.effective_to,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class DiscountRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    discountType: str = Field(..., max_length=32)
    fixedAmountMinor: Optional[int] = Field(None, ge=0)
    percentageBps: Optional[int] = Field(None, ge=0)
    scope: str = Field(default="society", max_length=32)
    oneTime: bool = False
    maxUses: Optional[int] = Field(None, ge=1)
    stackable: bool = False
    chargeHeadId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    occupancyId: Optional[UUID] = None
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("discountType")
    @classmethod
    def validate_discount_type(cls, value: str) -> str:
        return _normalize_enum(value, DISCOUNT_TYPE_VALUES, "discountType")

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        return _normalize_enum(value, DISCOUNT_SCOPE_VALUES, "scope")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_discount_fields(self) -> "DiscountRuleCreate":
        if self.discountType == "fixed" and self.fixedAmountMinor is None:
            raise ValueError("fixedAmountMinor is required for fixed discountType")
        if self.discountType == "percentage" and self.percentageBps is None:
            raise ValueError("percentageBps is required for percentage discountType")
        return self


class DiscountRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    discountType: Optional[str] = Field(None, max_length=32)
    fixedAmountMinor: Optional[int] = Field(None, ge=0)
    percentageBps: Optional[int] = Field(None, ge=0)
    scope: Optional[str] = Field(None, max_length=32)
    oneTime: Optional[bool] = None
    maxUses: Optional[int] = Field(None, ge=1)
    stackable: Optional[bool] = None
    chargeHeadId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    occupancyId: Optional[UUID] = None
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("discountType")
    @classmethod
    def validate_discount_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, DISCOUNT_TYPE_VALUES, "discountType")

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_enum(value, DISCOUNT_SCOPE_VALUES, "scope")


class DiscountRuleOut(BaseModel):
    id: UUID
    societyId: UUID
    chargeHeadId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    occupancyId: Optional[UUID] = None
    name: str
    discountType: str
    fixedAmountMinor: Optional[int] = None
    percentageBps: Optional[int] = None
    scope: str
    oneTime: bool
    maxUses: Optional[int] = None
    usesCount: int
    stackable: bool
    effectiveFrom: Optional[date] = None
    effectiveTo: Optional[date] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "DiscountRuleOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            chargeHeadId=row.charge_head_id,
            residentId=row.resident_id,
            occupancyId=row.occupancy_id,
            name=row.name,
            discountType=row.discount_type,
            fixedAmountMinor=row.fixed_amount_minor,
            percentageBps=row.percentage_bps,
            scope=row.scope,
            oneTime=row.one_time,
            maxUses=row.max_uses,
            usesCount=row.uses_count,
            stackable=row.stackable,
            effectiveFrom=row.effective_from,
            effectiveTo=row.effective_to,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------


class BillLineIn(BaseModel):
    chargeHeadId: UUID
    description: Optional[str] = Field(None, max_length=500)
    quantity: int = Field(1, ge=1)
    unitAmountMinor: int = Field(..., ge=0)
    taxMinor: int = Field(0, ge=0)
    discountMinor: int = Field(0, ge=0)
    isPenalty: bool = False
    isDiscount: bool = False
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class MaintenanceBillCreate(BaseModel):
    occupancyId: UUID
    financialYearId: UUID
    accountingPeriodId: Optional[UUID] = None
    billingCycleId: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=200)
    billDate: Optional[date] = None
    periodFrom: date
    periodTo: date
    dueDate: date
    currency: str = Field(default="INR", max_length=8)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    lines: List[BillLineIn] = Field(..., min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_period(self) -> "MaintenanceBillCreate":
        if self.periodTo < self.periodFrom:
            raise ValueError("periodTo must be on or after periodFrom")
        return self


class MaintenanceBillUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    billDate: Optional[date] = None
    periodFrom: Optional[date] = None
    periodTo: Optional[date] = None
    dueDate: Optional[date] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    lines: Optional[List[BillLineIn]] = None

    @field_validator("title", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BillGenerateRequest(BaseModel):
    cycleId: UUID
    financialYearId: UUID
    accountingPeriodId: Optional[UUID] = None
    periodFrom: date
    periodTo: date
    dueDate: date
    chargeHeadIds: List[UUID] = Field(..., min_length=1)
    occupancyIds: Optional[List[UUID]] = None
    autoPublish: bool = False
    title: Optional[str] = Field(None, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_period(self) -> "BillGenerateRequest":
        if self.periodTo < self.periodFrom:
            raise ValueError("periodTo must be on or after periodFrom")
        return self


class WriteOffRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    notes: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ApplyDiscountRequest(BaseModel):
    discountRuleId: Optional[UUID] = None
    amountMinor: Optional[int] = Field(None, ge=1)
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("description", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def require_source(self) -> "ApplyDiscountRequest":
        if self.discountRuleId is None and self.amountMinor is None:
            raise ValueError("discountRuleId or amountMinor is required")
        return self


class BillLineOut(BaseModel):
    id: UUID
    societyId: UUID
    billId: UUID
    chargeHeadId: UUID
    chargeHeadCode: Optional[str] = None
    chargeHeadName: Optional[str] = None
    lineNo: int
    description: str
    quantity: int
    unitAmountMinor: int
    lineTotalMinor: int
    taxMinor: int
    discountMinor: int
    isPenalty: bool
    isDiscount: bool
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(
        cls,
        row: Any,
        *,
        charge_head_code: Optional[str] = None,
        charge_head_name: Optional[str] = None,
    ) -> "BillLineOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            billId=row.bill_id,
            chargeHeadId=row.charge_head_id,
            chargeHeadCode=charge_head_code,
            chargeHeadName=charge_head_name,
            lineNo=row.line_no,
            description=row.description,
            quantity=row.quantity,
            unitAmountMinor=row.unit_amount_minor,
            lineTotalMinor=row.line_total_minor,
            taxMinor=row.tax_minor,
            discountMinor=row.discount_minor,
            isPenalty=row.is_penalty,
            isDiscount=row.is_discount,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class MaintenanceBillOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    wingId: UUID
    flatId: UUID
    occupancyId: UUID
    residentId: UUID
    billingCycleId: Optional[UUID] = None
    financialYearId: UUID
    accountingPeriodId: Optional[UUID] = None
    billNumber: str
    title: str
    status: str
    billDate: date
    periodFrom: date
    periodTo: date
    dueDate: date
    grossMinor: int
    discountMinor: int
    penaltyMinor: int
    taxMinor: int
    netMinor: int
    paidMinor: int
    outstandingMinor: int
    currency: str
    publishedAt: Optional[datetime] = None
    cancelledAt: Optional[datetime] = None
    writtenOffAt: Optional[datetime] = None
    writeOffReason: Optional[str] = None
    source: str
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    residentName: Optional[str] = None
    flatNo: Optional[str] = None
    wingCode: Optional[str] = None
    buildingName: Optional[str] = None
    lines: Optional[List[BillLineOut]] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(
        cls,
        row: Any,
        *,
        resident_name: Optional[str] = None,
        flat_no: Optional[str] = None,
        wing_code: Optional[str] = None,
        building_name: Optional[str] = None,
        lines: Optional[List[BillLineOut]] = None,
    ) -> "MaintenanceBillOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            buildingId=row.building_id,
            wingId=row.wing_id,
            flatId=row.flat_id,
            occupancyId=row.occupancy_id,
            residentId=row.resident_id,
            billingCycleId=row.billing_cycle_id,
            financialYearId=row.financial_year_id,
            accountingPeriodId=row.accounting_period_id,
            billNumber=row.bill_number,
            title=row.title,
            status=row.status,
            billDate=row.bill_date,
            periodFrom=row.period_from,
            periodTo=row.period_to,
            dueDate=row.due_date,
            grossMinor=row.gross_minor,
            discountMinor=row.discount_minor,
            penaltyMinor=row.penalty_minor,
            taxMinor=row.tax_minor,
            netMinor=row.net_minor,
            paidMinor=row.paid_minor,
            outstandingMinor=row.outstanding_minor,
            currency=row.currency,
            publishedAt=row.published_at,
            cancelledAt=row.cancelled_at,
            writtenOffAt=row.written_off_at,
            writeOffReason=row.write_off_reason,
            source=row.source,
            notes=row.notes,
            metadata=row.metadata_json or {},
            residentName=resident_name,
            flatNo=flat_no,
            wingCode=wing_code,
            buildingName=building_name,
            lines=lines,
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


# ---------------------------------------------------------------------------
# Payments & receipts
# ---------------------------------------------------------------------------


class PaymentAllocationIn(BaseModel):
    billId: Optional[UUID] = None
    amountMinor: int = Field(..., ge=1)
    allocationType: str = Field(default="bill", max_length=32)
    notes: Optional[str] = None

    @field_validator("allocationType")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return _normalize_enum(value, ALLOCATION_TYPE_VALUES, "allocationType")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_bill(self) -> "PaymentAllocationIn":
        if self.allocationType == "bill" and self.billId is None:
            raise ValueError("billId is required for bill allocation")
        return self


class PaymentCreate(BaseModel):
    residentId: UUID
    occupancyId: Optional[UUID] = None
    financialYearId: UUID
    accountingPeriodId: Optional[UUID] = None
    amountMinor: int = Field(..., ge=1)
    mode: str = Field(..., max_length=32)
    paymentDate: Optional[datetime] = None
    valueDate: Optional[date] = None
    externalReference: Optional[str] = Field(None, max_length=128)
    chequeNumber: Optional[str] = Field(None, max_length=64)
    bankName: Optional[str] = Field(None, max_length=128)
    upiVpa: Optional[str] = Field(None, max_length=128)
    gatewayProvider: Optional[str] = Field(None, max_length=64)
    gatewayTxnId: Optional[str] = Field(None, max_length=128)
    idempotencyKey: Optional[str] = Field(None, max_length=128)
    payerName: Optional[str] = Field(None, max_length=200)
    collectedByStaffId: Optional[UUID] = None
    currency: str = Field(default="INR", max_length=8)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    allocations: Optional[List[PaymentAllocationIn]] = None
    autoAllocate: bool = True

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        return _normalize_enum(value, PAYMENT_MODE_VALUES, "mode")

    @field_validator(
        "externalReference",
        "chequeNumber",
        "bankName",
        "upiVpa",
        "gatewayProvider",
        "gatewayTxnId",
        "idempotencyKey",
        "payerName",
        "notes",
    )
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class PaymentAllocateRequest(BaseModel):
    allocations: List[PaymentAllocationIn] = Field(..., min_length=1)


class PaymentAllocationOut(BaseModel):
    id: UUID
    societyId: UUID
    paymentId: UUID
    billId: Optional[UUID] = None
    allocationType: str
    amountMinor: int
    allocatedAt: datetime
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    isActive: bool
    createdAt: datetime

    @classmethod
    def from_orm(cls, row: Any) -> "PaymentAllocationOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            paymentId=row.payment_id,
            billId=row.bill_id,
            allocationType=row.allocation_type,
            amountMinor=row.amount_minor,
            allocatedAt=row.allocated_at,
            notes=row.notes,
            metadata=row.metadata_json or {},
            isActive=row.is_active,
            createdAt=row.created_at,
        )


class PaymentOut(BaseModel):
    id: UUID
    societyId: UUID
    residentId: UUID
    occupancyId: Optional[UUID] = None
    collectedBy: Optional[UUID] = None
    collectedByStaffId: Optional[UUID] = None
    financialYearId: UUID
    accountingPeriodId: Optional[UUID] = None
    reversedPaymentId: Optional[UUID] = None
    paymentNumber: str
    amountMinor: int
    unallocatedMinor: int
    currency: str
    mode: str
    status: str
    paymentDate: datetime
    valueDate: Optional[date] = None
    externalReference: Optional[str] = None
    chequeNumber: Optional[str] = None
    bankName: Optional[str] = None
    upiVpa: Optional[str] = None
    gatewayProvider: Optional[str] = None
    gatewayTxnId: Optional[str] = None
    idempotencyKey: Optional[str] = None
    payerName: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    residentName: Optional[str] = None
    allocations: Optional[List[PaymentAllocationOut]] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(
        cls,
        row: Any,
        *,
        resident_name: Optional[str] = None,
        allocations: Optional[List[PaymentAllocationOut]] = None,
    ) -> "PaymentOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            residentId=row.resident_id,
            occupancyId=row.occupancy_id,
            collectedBy=row.collected_by,
            collectedByStaffId=row.collected_by_staff_id,
            financialYearId=row.financial_year_id,
            accountingPeriodId=row.accounting_period_id,
            reversedPaymentId=row.reversed_payment_id,
            paymentNumber=row.payment_number,
            amountMinor=row.amount_minor,
            unallocatedMinor=row.unallocated_minor,
            currency=row.currency,
            mode=row.mode,
            status=row.status,
            paymentDate=row.payment_date,
            valueDate=row.value_date,
            externalReference=row.external_reference,
            chequeNumber=row.cheque_number,
            bankName=row.bank_name,
            upiVpa=row.upi_vpa,
            gatewayProvider=row.gateway_provider,
            gatewayTxnId=row.gateway_txn_id,
            idempotencyKey=row.idempotency_key,
            payerName=row.payer_name,
            notes=row.notes,
            metadata=row.metadata_json or {},
            residentName=resident_name,
            allocations=allocations,
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class ReceiptOut(BaseModel):
    id: UUID
    societyId: UUID
    paymentId: UUID
    residentId: UUID
    financialYearId: UUID
    receiptNumber: str
    issuedAt: datetime
    issuedBy: Optional[UUID] = None
    amountMinor: int
    currency: str
    pdfUrl: Optional[str] = None
    isVoid: bool
    notes: Optional[str] = None
    metadata: Dict[str, Any]
    residentName: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm(
        cls,
        row: Any,
        *,
        resident_name: Optional[str] = None,
    ) -> "ReceiptOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            paymentId=row.payment_id,
            residentId=row.resident_id,
            financialYearId=row.financial_year_id,
            receiptNumber=row.receipt_number,
            issuedAt=row.issued_at,
            issuedBy=row.issued_by,
            amountMinor=row.amount_minor,
            currency=row.currency,
            pdfUrl=row.pdf_url,
            isVoid=row.is_void,
            notes=row.notes,
            metadata=row.metadata_json or {},
            residentName=resident_name,
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )
