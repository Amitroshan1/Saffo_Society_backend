"""Building schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.building import BuildingCreate


def test_building_code_uppercase_and_valid():
    body = BuildingCreate(name="Tower One", code="tower_1")
    assert body.code == "TOWER_1"


def test_building_invalid_status_rejected():
    with pytest.raises(ValidationError):
        BuildingCreate(name="Tower Two", code="B", status="disabled")


def test_building_units_consistency():
    with pytest.raises(ValidationError):
        BuildingCreate(
            name="Tower Three",
            code="C",
            plannedUnits=100,
            occupiedUnits=70,
            vacantUnits=40,
        )
