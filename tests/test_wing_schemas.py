"""Wing schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.wing import WingCreate


def test_wing_code_uppercase():
    body = WingCreate(
        buildingId="00000000-0000-0000-0000-000000000001",
        name="Wing One",
        code="wing_1",
    )
    assert body.code == "WING_1"


def test_wing_invalid_color():
    with pytest.raises(ValidationError):
        WingCreate(
            buildingId="00000000-0000-0000-0000-000000000001",
            name="Wing Two",
            code="W2",
            color="blue",
        )


def test_wing_optional_enhancements():
    body = WingCreate(
        buildingId="00000000-0000-0000-0000-000000000001",
        name="Wing Three",
        code="W3",
        shortCode="W3",
        sequence=5,
        color="#ABC",
        capacity=40,
    )
    assert body.shortCode == "W3"
    assert body.sequence == 5
    assert body.color == "#ABC"
