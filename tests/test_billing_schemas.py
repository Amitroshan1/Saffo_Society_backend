"""Billing schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.billing import (
    BillGenerateRequest,
    ChargeHeadCreate,
    MaintenanceBillCreate,
    PaymentCreate,
)


def test_charge_head_category_normalized():
    body = ChargeHeadCreate(
        code="maint",
        name="Maintenance",
        category="Sinking Fund",
        defaultAmountMinor=10000,
    )
    assert body.code == "MAINT"
    assert body.category == "sinking_fund"


def test_charge_head_invalid_category():
    with pytest.raises(ValidationError):
        ChargeHeadCreate(code="X", name="X", category="invalid_cat")


def test_charge_head_money_non_negative():
    with pytest.raises(ValidationError):
        ChargeHeadCreate(
            code="X",
            name="X",
            category="maintenance",
            defaultAmountMinor=-1,
        )


def test_bill_generate_period_order():
    with pytest.raises(ValidationError):
        BillGenerateRequest(
            cycleId="00000000-0000-0000-0000-000000000001",
            financialYearId="00000000-0000-0000-0000-000000000002",
            periodFrom="2026-07-31",
            periodTo="2026-07-01",
            dueDate="2026-08-10",
            chargeHeadIds=["00000000-0000-0000-0000-000000000003"],
        )


def test_bill_generate_requires_charge_heads():
    with pytest.raises(ValidationError):
        BillGenerateRequest(
            cycleId="00000000-0000-0000-0000-000000000001",
            financialYearId="00000000-0000-0000-0000-000000000002",
            periodFrom="2026-07-01",
            periodTo="2026-07-31",
            dueDate="2026-08-10",
            chargeHeadIds=[],
        )


def test_manual_bill_requires_lines():
    with pytest.raises(ValidationError):
        MaintenanceBillCreate(
            occupancyId="00000000-0000-0000-0000-000000000001",
            financialYearId="00000000-0000-0000-0000-000000000002",
            title="Test",
            periodFrom="2026-07-01",
            periodTo="2026-07-31",
            dueDate="2026-08-10",
            lines=[],
        )


def test_payment_mode_normalized():
    body = PaymentCreate(
        residentId="00000000-0000-0000-0000-000000000001",
        financialYearId="00000000-0000-0000-0000-000000000002",
        amountMinor=50000,
        mode="Bank Transfer",
    )
    assert body.mode == "bank_transfer"


def test_payment_invalid_mode():
    with pytest.raises(ValidationError):
        PaymentCreate(
            residentId="00000000-0000-0000-0000-000000000001",
            financialYearId="00000000-0000-0000-0000-000000000002",
            amountMinor=100,
            mode="bitcoin",
        )


def test_payment_amount_positive():
    with pytest.raises(ValidationError):
        PaymentCreate(
            residentId="00000000-0000-0000-0000-000000000001",
            financialYearId="00000000-0000-0000-0000-000000000002",
            amountMinor=0,
            mode="cash",
        )
