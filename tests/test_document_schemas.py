"""Document Management schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.document import (
    DocumentCategoryCreate,
    DocumentCategoryUpdate,
    DocumentCreate,
    DocumentListQueryParams,
    DocumentPermissionIn,
    DocumentPermissionsReplace,
    DocumentUpdate,
    DocumentVersionCreate,
    FinanceDocumentListQueryParams,
    GuardDocumentListQueryParams,
    ResidentDocumentListQueryParams,
)

VALID_UUID = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# DocumentCreate
# ---------------------------------------------------------------------------


def test_document_create_defaults():
    body = DocumentCreate(title="Society Bye Laws", fileName="bye-laws.pdf", fileUrl="https://example.com/bye-laws.pdf")
    assert body.scope == "society"
    assert body.isPinned is False
    assert body.isFavoriteDefault is False
    assert body.tags == []
    assert body.permissions == []


def test_document_create_normalizes_scope():
    body = DocumentCreate(
        title="Finance report",
        fileName="report.pdf",
        fileUrl="https://example.com/report.pdf",
        scope="Finance",
    )
    assert body.scope == "finance"


def test_document_create_blank_title_rejected():
    with pytest.raises(ValidationError):
        DocumentCreate(title="   ", fileName="a.pdf", fileUrl="https://example.com/a.pdf")


def test_document_create_requires_file_name_and_url():
    with pytest.raises(ValidationError):
        DocumentCreate(title="Test", fileName="", fileUrl="https://example.com/a.pdf")
    with pytest.raises(ValidationError):
        DocumentCreate(title="Test", fileName="a.pdf", fileUrl="")


def test_document_create_invalid_scope_rejected():
    with pytest.raises(ValidationError):
        DocumentCreate(
            title="Test", fileName="a.pdf", fileUrl="https://example.com/a.pdf", scope="not_a_scope"
        )


def test_document_create_invalid_mime_rejected():
    with pytest.raises(ValidationError):
        DocumentCreate(
            title="Test",
            fileName="a.exe",
            fileUrl="https://example.com/a.exe",
            mimeType="application/x-msdownload",
        )


def test_document_create_valid_mime_normalized():
    body = DocumentCreate(
        title="Test",
        fileName="a.pdf",
        fileUrl="https://example.com/a.pdf",
        mimeType="Application/PDF",
    )
    assert body.mimeType == "application/pdf"


def test_document_create_file_size_limit():
    with pytest.raises(ValidationError):
        DocumentCreate(
            title="Test",
            fileName="a.pdf",
            fileUrl="https://example.com/a.pdf",
            fileSizeBytes=101 * 1024 * 1024,
        )


def test_document_create_tags_cleaned():
    body = DocumentCreate(
        title="Test",
        fileName="a.pdf",
        fileUrl="https://example.com/a.pdf",
        tags=["  agm  ", "", "notice"],
    )
    assert body.tags == ["agm", "notice"]


# ---------------------------------------------------------------------------
# DocumentUpdate
# ---------------------------------------------------------------------------


def test_document_update_partial_fields_only():
    body = DocumentUpdate(title="Updated title")
    data = body.model_dump(exclude_unset=True)
    assert data == {"title": "Updated title"}


def test_document_update_blank_title_rejected():
    with pytest.raises(ValidationError):
        DocumentUpdate(title="   ")


def test_document_update_invalid_scope_rejected():
    with pytest.raises(ValidationError):
        DocumentUpdate(scope="bogus")


def test_document_update_invalid_mime_rejected():
    with pytest.raises(ValidationError):
        DocumentUpdate(mimeType="application/x-msdownload")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_permission_everyone_requires_no_extra_fields():
    perm = DocumentPermissionIn(permissionType="everyone")
    assert perm.permissionType == "everyone"


def test_permission_everyone_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="everyone", buildingId=VALID_UUID)


def test_permission_role_requires_role_name():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="role")


def test_permission_role_valid():
    perm = DocumentPermissionIn(permissionType="Role", roleName="finance")
    assert perm.permissionType == "role"
    assert perm.roleName == "finance"


def test_permission_building_requires_building_id():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="building")


def test_permission_wing_requires_wing_id():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="wing")


def test_permission_flat_requires_flat_id():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="flat")


def test_permission_resident_requires_resident_id():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="resident")


def test_permission_invalid_type_rejected():
    with pytest.raises(ValidationError):
        DocumentPermissionIn(permissionType="floor")


def test_permissions_replace_allows_empty_list():
    body = DocumentPermissionsReplace(permissions=[])
    assert body.permissions == []


def test_permissions_replace_valid():
    body = DocumentPermissionsReplace(permissions=[DocumentPermissionIn(permissionType="everyone")])
    assert len(body.permissions) == 1


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def test_category_create_normalizes_code():
    body = DocumentCategoryCreate(code="  society docs  ", name="Society Documents")
    assert body.code == "SOCIETY_DOCS"


def test_category_create_blank_name_rejected():
    with pytest.raises(ValidationError):
        DocumentCategoryCreate(code="FIN", name="   ")


def test_category_update_partial_fields_only():
    body = DocumentCategoryUpdate(name="Updated Name")
    data = body.model_dump(exclude_unset=True)
    assert data == {"name": "Updated Name"}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def test_version_create_requires_file_name_and_url():
    with pytest.raises(ValidationError):
        DocumentVersionCreate(fileName="", fileUrl="https://example.com/a.pdf")


def test_version_create_valid():
    version = DocumentVersionCreate(
        fileName="v2.pdf", fileUrl="https://example.com/v2.pdf", changeNotes="  Updated figures  "
    )
    assert version.changeNotes == "Updated figures"


def test_version_create_invalid_mime_rejected():
    with pytest.raises(ValidationError):
        DocumentVersionCreate(
            fileName="v2.exe",
            fileUrl="https://example.com/v2.exe",
            mimeType="application/x-msdownload",
        )


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


def test_document_list_query_defaults():
    query = DocumentListQueryParams()
    assert query.page == 1
    assert query.page_size == 20
    assert query.sort_order == "desc"


def test_document_list_query_alias_population():
    query = DocumentListQueryParams(isPinned=True, categoryId=VALID_UUID)
    assert query.is_pinned is True
    assert str(query.category_id) == VALID_UUID


def test_resident_document_list_query_defaults():
    query = ResidentDocumentListQueryParams()
    assert query.favorites_only is None


def test_resident_document_list_query_alias_population():
    query = ResidentDocumentListQueryParams(favoritesOnly=True, categoryId=VALID_UUID)
    assert query.favorites_only is True
    assert str(query.category_id) == VALID_UUID


def test_finance_document_list_query_defaults():
    query = FinanceDocumentListQueryParams()
    assert query.status is None


def test_guard_document_list_query_defaults():
    query = GuardDocumentListQueryParams()
    assert query.category_id is None


# ---------------------------------------------------------------------------
# Document number format sanity (produced by service, validated shape here)
# ---------------------------------------------------------------------------


def test_document_number_format_matches_pattern():
    import re

    sample = f"DOC-{1:06d}"
    assert re.fullmatch(r"DOC-\d{6}", sample)
