"""Complaint schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.complaint import (
    ComplaintAssign,
    ComplaintCommentCreate,
    ComplaintCreate,
    ComplaintPriorityUpdate,
    ComplaintStatusUpdate,
)


def test_complaint_create_category_normalized():
    body = ComplaintCreate(
        category="Common Area",
        title="Broken light",
        description="Corridor light not working on 3rd floor",
    )
    assert body.category == "common_area"
    assert body.priority == "medium"


def test_complaint_invalid_priority():
    with pytest.raises(ValidationError):
        ComplaintCreate(
            category="electrical",
            title="Issue",
            description="Details",
            priority="urgent",
        )


def test_complaint_status_update_normalizes():
    body = ComplaintStatusUpdate(status="In Progress")
    assert body.status == "in_progress"


def test_complaint_assign_schema():
    body = ComplaintAssign(staffId="00000000-0000-0000-0000-000000000001")
    assert body.staffId


def test_complaint_comment_requires_message():
    with pytest.raises(ValidationError):
        ComplaintCommentCreate(message="   ")


def test_complaint_priority_update():
    body = ComplaintPriorityUpdate(priority="Critical")
    assert body.priority == "critical"
