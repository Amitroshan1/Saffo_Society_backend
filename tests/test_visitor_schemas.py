"""Visitor schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.visitor import VisitorCreate, VisitorUpdate


def test_visitor_create_name_and_phone_trim():
    body = VisitorCreate(name="  John Doe ", phone=" 9990011223 ")
    assert body.name == "John Doe"
    assert body.phone == "9990011223"


def test_visitor_create_metadata_default():
    body = VisitorCreate(name="Jane", phone="9990011224")
    assert body.metadata == {}


def test_visitor_update_extra_ignored():
    body = VisitorUpdate(name="Changed", extraField="x")  # type: ignore[call-arg]
    dumped = body.model_dump(exclude_unset=True)
    assert dumped == {"name": "Changed"}


def test_visitor_email_validation():
    with pytest.raises(ValidationError):
        VisitorCreate(name="John", phone="9990011224", email="invalid")
