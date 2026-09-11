"""Staff/gate/shift schema validation tests (no DB)."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from Schemas.gate import GateCreate
from Schemas.shift import ShiftCreate
from Schemas.staff import StaffCreate, StaffUpdate


def test_staff_role_normalized():
    body = StaffCreate(name="Guard One", phone="9000012345", staffRole="Security_Guard")
    assert body.staffRole == "security_guard"


def test_staff_invalid_role():
    with pytest.raises(ValidationError):
        StaffCreate(name="X", phone="9000012345", staffRole="ceo")


def test_staff_update_extra_ignored():
    body = StaffUpdate(name="Updated", unknownField="x")  # type: ignore[call-arg]
    assert body.model_dump(exclude_unset=True) == {"name": "Updated"}


def test_gate_code_uppercased():
    body = GateCreate(code="main", name="Main Gate", gateType="Main")
    assert body.code == "MAIN"
    assert body.gateType == "main"


def test_shift_end_must_be_after_start_validated_in_service_not_schema():
    # Schema allows; service enforces chronology. Ensure create schema accepts times.
    start = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc)
    body = ShiftCreate(
        staffId="00000000-0000-0000-0000-000000000001",
        shiftDate=date(2026, 7, 28),
        shiftType="Morning",
        scheduledStart=start,
        scheduledEnd=end,
    )
    assert body.shiftType == "morning"
