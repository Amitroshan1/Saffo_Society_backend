"""Society schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.society import SocietyCreate


def test_society_create_requires_address():
    with pytest.raises(ValidationError):
        SocietyCreate(
            name="Test",
            code="TEST-01",
            addressLine1="",
            city="Pune",
            state="MH",
            pincode="411001",
        )


def test_society_gstin_validated_for_india():
    with pytest.raises(ValidationError):
        SocietyCreate(
            name="Test Society",
            code="TEST-02",
            addressLine1="1 Main St",
            city="Pune",
            state="Maharashtra",
            pincode="411001",
            country="IN",
            gstin="INVALID",
        )


def test_society_create_ok():
    body = SocietyCreate(
        name="Green Park Society",
        code="GREEN-PARK",
        addressLine1="12 Lake Road",
        city="Pune",
        state="Maharashtra",
        pincode="411001",
        country="IN",
    )
    assert body.code == "GREEN-PARK"
    assert body.country == "IN"
