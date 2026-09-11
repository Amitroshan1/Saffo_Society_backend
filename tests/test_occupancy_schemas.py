"""Occupancy schema validation tests (no DB)."""

from datetime import date

import pytest
from pydantic import ValidationError

from Schemas.occupancy import OccupancyCreate, OccupancyMoveOut, OccupancyUpdate


def test_occupancy_role_normalized():
    body = OccupancyCreate(
        flatId="00000000-0000-0000-0000-000000000001",
        residentId="00000000-0000-0000-0000-000000000002",
        role="Tenant",
        moveInDate=date(2026, 1, 1),
    )
    assert body.role == "tenant"


def test_domestic_help_cannot_be_primary():
    with pytest.raises(ValidationError):
        OccupancyCreate(
            flatId="00000000-0000-0000-0000-000000000001",
            residentId="00000000-0000-0000-0000-000000000002",
            role="domestic_help",
            moveInDate=date(2026, 1, 1),
            isPrimary=True,
        )


def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        OccupancyCreate(
            flatId="00000000-0000-0000-0000-000000000001",
            residentId="00000000-0000-0000-0000-000000000002",
            role="landlord",
            moveInDate=date(2026, 1, 1),
        )


def test_move_out_default_reason():
    body = OccupancyMoveOut()
    assert body.endedReason == "moved_out"


def test_occupancy_update_role_optional():
    body = OccupancyUpdate(isPrimary=True)
    assert body.isPrimary is True
    assert body.role is None
