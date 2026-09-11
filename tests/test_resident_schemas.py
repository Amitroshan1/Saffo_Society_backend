"""Resident schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.resident import ResidentCreate, ResidentUpdate


def test_resident_name_required():
    with pytest.raises(ValidationError):
        ResidentCreate(name="   ")


def test_resident_create_strips_phone():
    body = ResidentCreate(name="Jane Doe", phone="  9876543210  ")
    assert body.phone == "9876543210"


def test_resident_update_extra_ignored():
    body = ResidentUpdate(name="Updated", unknownField="x")  # type: ignore[call-arg]
    dumped = body.model_dump(exclude_unset=True)
    assert dumped == {"name": "Updated"}


def test_resident_metadata_defaults():
    body = ResidentCreate(name="John")
    assert body.metadata == {}
