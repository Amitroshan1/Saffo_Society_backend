"""Resident portal schema validation tests."""

import pytest
from pydantic import ValidationError

from Schemas.resident_portal import (
    ResidentVisitorApprovalRequest,
    ResidentVisitorInvitationCreate,
)


def test_invitation_accepts_embedded_visitor():
    body = ResidentVisitorInvitationCreate(
        visitor={"name": "Guest One", "phone": "9999999999"},
        purpose="Family visit",
        visitorType="Guest",
    )
    assert body.visitorType == "guest"


def test_invitation_invalid_visitor_type():
    with pytest.raises(ValidationError):
        ResidentVisitorInvitationCreate(
            visitor={"name": "Guest One", "phone": "9999999999"},
            purpose="Family visit",
            visitorType="unknown",
        )


def test_visitor_approval_action_enum():
    body = ResidentVisitorApprovalRequest(
        visitId="00000000-0000-0000-0000-000000000001",
        action="approve",
    )
    assert body.action == "approve"

    with pytest.raises(ValidationError):
        ResidentVisitorApprovalRequest(
            visitId="00000000-0000-0000-0000-000000000001",
            action="archive",
        )
