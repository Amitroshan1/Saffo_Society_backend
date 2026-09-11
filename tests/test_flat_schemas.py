"""Flat schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.flat import FlatCreate, FlatUpdate


def test_flat_no_uppercase():
    body = FlatCreate(
        wingId="00000000-0000-0000-0000-000000000001",
        flatNo="a-101",
        floorNo="1",
    )
    assert body.flatNo == "A-101"


def test_flat_invalid_color():
    with pytest.raises(ValidationError):
        FlatCreate(
            wingId="00000000-0000-0000-0000-000000000001",
            flatNo="101",
            floorNo="1",
            color="blue",
        )


def test_flat_usage_type_and_metadata():
    body = FlatCreate(
        wingId="00000000-0000-0000-0000-000000000001",
        flatNo="102",
        floorNo="G",
        usageType="Residential",
        flatType="2BHK",
        status="vacant",
        ownershipType="owned",
        areaSqft=850.5,
        areaType="carpet",
        sequence=2,
        color="#ABC",
        metadata={
            "utilities": {
                "electricityMeter": "EL-001",
                "waterMeter": "WT-001",
            }
        },
    )
    assert body.usageType == "residential"
    assert body.flatType == "2bhk"
    assert body.floorNo == "G"
    assert body.metadata["utilities"]["electricityMeter"] == "EL-001"


def test_flat_update_excludes_flat_no_and_wing():
    body = FlatUpdate(floorNo="2", status="occupied", flatNo="999")  # type: ignore[call-arg]
    dumped = body.model_dump(exclude_unset=True)
    assert "flatNo" not in dumped
    assert "wingId" not in dumped
    assert dumped["floorNo"] == "2"


def test_flat_invalid_usage_type():
    with pytest.raises(ValidationError):
        FlatCreate(
            wingId="00000000-0000-0000-0000-000000000001",
            flatNo="103",
            floorNo="1",
            usageType="industrial",
        )
