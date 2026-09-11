"""Visit schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.visit import VisitCreate, VisitUpdate


def test_visit_create_normalizes_type_and_status():
    body = VisitCreate(
        occupancyId="00000000-0000-0000-0000-000000000001",
        visitorId="00000000-0000-0000-0000-000000000002",
        purpose="Family visit",
        visitorType="Guest",
        status="Scheduled",
    )
    assert body.visitorType == "guest"
    assert body.status == "scheduled"


def test_visit_invalid_visitor_type():
    with pytest.raises(ValidationError):
        VisitCreate(
            occupancyId="00000000-0000-0000-0000-000000000001",
            visitorId="00000000-0000-0000-0000-000000000002",
            purpose="Family visit",
            visitorType="friend",
            status="scheduled",
        )


def test_visit_invalid_pass_type():
    with pytest.raises(ValidationError):
        VisitCreate(
            occupancyId="00000000-0000-0000-0000-000000000001",
            visitorId="00000000-0000-0000-0000-000000000002",
            purpose="Family visit",
            visitorType="guest",
            passType="gold",
            status="scheduled",
        )


def test_visit_update_trims_fields():
    body = VisitUpdate(purpose="  plumber visit  ", notes="  urgent  ")
    assert body.purpose == "plumber visit"
    assert body.notes == "urgent"


def test_visit_create_number_of_people_bounds():
    with pytest.raises(ValidationError):
        VisitCreate(
            occupancyId="00000000-0000-0000-0000-000000000001",
            visitorId="00000000-0000-0000-0000-000000000002",
            purpose="Family visit",
            visitorType="guest",
            status="scheduled",
            numberOfPeople=0,
        )
