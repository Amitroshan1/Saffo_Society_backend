"""Notice schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.notice import (
    NoticeAttachmentIn,
    NoticeCancelRequest,
    NoticeCreate,
    NoticeListQueryParams,
    NoticePinRequest,
    NoticeTargetIn,
    NoticeTargetsReplace,
    NoticeUpdate,
    ResidentNoticeListQueryParams,
)

VALID_UUID = "00000000-0000-0000-0000-000000000001"


def test_notice_create_defaults():
    body = NoticeCreate(title="Water shutdown notice")
    assert body.category == "general"
    assert body.priority == "normal"
    assert body.bodyText == ""
    assert body.isPinned is False
    assert body.requiresAcknowledgement is False
    assert body.targets == []
    assert body.attachments == []


def test_notice_create_normalizes_category_and_priority():
    body = NoticeCreate(title="Society AGM", category="Committee", priority="High")
    assert body.category == "committee"
    assert body.priority == "high"


def test_notice_create_blank_title_rejected():
    with pytest.raises(ValidationError):
        NoticeCreate(title="   ")


def test_notice_create_invalid_category_rejected():
    with pytest.raises(ValidationError):
        NoticeCreate(title="Test", category="not_a_category")


def test_notice_create_invalid_priority_rejected():
    with pytest.raises(ValidationError):
        NoticeCreate(title="Test", priority="urgent")


def test_notice_create_expires_before_publish_rejected():
    with pytest.raises(ValidationError):
        NoticeCreate(
            title="Test",
            publishAt="2026-08-10T00:00:00Z",
            expiresAt="2026-08-01T00:00:00Z",
        )


def test_notice_create_expires_after_publish_ok():
    body = NoticeCreate(
        title="Test",
        publishAt="2026-08-01T00:00:00Z",
        expiresAt="2026-08-10T00:00:00Z",
    )
    assert body.expiresAt > body.publishAt


def test_notice_update_partial_fields_only():
    body = NoticeUpdate(title="Updated title")
    data = body.model_dump(exclude_unset=True)
    assert data == {"title": "Updated title"}


def test_notice_update_blank_title_rejected():
    with pytest.raises(ValidationError):
        NoticeUpdate(title="   ")


def test_notice_update_invalid_category_rejected():
    with pytest.raises(ValidationError):
        NoticeUpdate(category="bogus")


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


def test_target_society_requires_no_ids():
    target = NoticeTargetIn(targetType="society")
    assert target.targetType == "society"


def test_target_society_rejects_extra_ids():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="society", buildingId=VALID_UUID)


def test_target_building_requires_building_id():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="building")


def test_target_building_valid():
    target = NoticeTargetIn(targetType="Building", buildingId=VALID_UUID)
    assert target.targetType == "building"
    assert str(target.buildingId) == VALID_UUID


def test_target_wing_requires_wing_id():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="wing")


def test_target_flat_requires_flat_id():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="flat")


def test_target_resident_requires_resident_id():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="resident")


def test_target_committee_role_requires_role():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="committee_role")


def test_target_committee_role_valid():
    target = NoticeTargetIn(targetType="committee_role", committeeRole="secretary")
    assert target.committeeRole == "secretary"


def test_target_invalid_type_rejected():
    with pytest.raises(ValidationError):
        NoticeTargetIn(targetType="floor")


def test_targets_replace_requires_at_least_one():
    with pytest.raises(ValidationError):
        NoticeTargetsReplace(targets=[])


def test_targets_replace_valid():
    body = NoticeTargetsReplace(targets=[NoticeTargetIn(targetType="society")])
    assert len(body.targets) == 1


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


def test_attachment_requires_file_name_and_url():
    with pytest.raises(ValidationError):
        NoticeAttachmentIn(fileName="", fileUrl="https://example.com/a.pdf")


def test_attachment_valid_mime():
    att = NoticeAttachmentIn(
        fileName="notice.pdf",
        fileUrl="https://example.com/notice.pdf",
        mimeType="application/pdf",
    )
    assert att.mimeType == "application/pdf"


def test_attachment_invalid_mime_rejected():
    with pytest.raises(ValidationError):
        NoticeAttachmentIn(
            fileName="notice.exe",
            fileUrl="https://example.com/notice.exe",
            mimeType="application/x-msdownload",
        )


def test_attachment_size_limit():
    with pytest.raises(ValidationError):
        NoticeAttachmentIn(
            fileName="big.pdf",
            fileUrl="https://example.com/big.pdf",
            fileSizeBytes=11 * 1024 * 1024,
        )


# ---------------------------------------------------------------------------
# Cancel / pin requests
# ---------------------------------------------------------------------------


def test_cancel_request_optional_reason():
    body = NoticeCancelRequest()
    assert body.reason is None


def test_cancel_request_strips_reason():
    body = NoticeCancelRequest(reason="  Event postponed  ")
    assert body.reason == "Event postponed"


def test_pin_request_optional_until():
    body = NoticePinRequest()
    assert body.pinUntil is None


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


def test_notice_list_query_defaults():
    query = NoticeListQueryParams()
    assert query.page == 1
    assert query.page_size == 20
    assert query.sort_order == "desc"


def test_notice_list_query_alias_population():
    query = NoticeListQueryParams(isPinned=True, buildingId=VALID_UUID)
    assert query.is_pinned is True
    assert str(query.building_id) == VALID_UUID


def test_resident_notice_list_query_defaults():
    query = ResidentNoticeListQueryParams()
    assert query.view is None
    assert query.unread_only is None


def test_resident_notice_list_query_alias_population():
    query = ResidentNoticeListQueryParams(unreadOnly=True, view="pinned")
    assert query.unread_only is True
    assert query.view == "pinned"
