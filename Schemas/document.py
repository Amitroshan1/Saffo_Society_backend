"""Pydantic schemas for Document Management System (Phase 12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Schemas.common import ListQueryParams
from Schemas.guard_document_schema import GuardDocumentListQueryParams
from Schemas.resident_document_schema import ResidentDocumentListQueryParams

DOCUMENT_STATUS_VALUES = (
    "draft",
    "published",
    "archived",
    "expired",
    "deleted",
)
DOCUMENT_SCOPE_VALUES = (
    "society",
    "building",
    "wing",
    "flat",
    "finance",
    "guard",
    "committee",
    "other",
)
DOCUMENT_PERMISSION_TYPE_VALUES = (
    "everyone",
    "role",
    "building",
    "wing",
    "flat",
    "resident",
)

ALLOWED_DOC_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "text/plain",
    "text/csv",
}


def _norm_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


class DocumentListQueryParams(ListQueryParams):
    status: Optional[str] = None
    category_id: Optional[UUID] = Field(None, alias="categoryId")
    scope: Optional[str] = None
    is_pinned: Optional[bool] = Field(None, alias="isPinned")
    from_date: Optional[datetime] = Field(None, alias="from")
    to_date: Optional[datetime] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


class FinanceDocumentListQueryParams(ListQueryParams):
    status: Optional[str] = None
    category_id: Optional[UUID] = Field(None, alias="categoryId")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class DocumentCategoryCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=120)
    parentId: Optional[UUID] = None
    displayOrder: int = Field(default=0, ge=0)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=64)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().upper().replace(" ", "_")
        if not value:
            raise ValueError("code cannot be blank")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("description", "icon")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    parentId: Optional[UUID] = None
    displayOrder: Optional[int] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=64)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("description", "icon")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class DocumentPermissionIn(BaseModel):
    permissionType: str = Field(..., max_length=32)
    roleName: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    wingId: Optional[UUID] = None
    flatId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    canDownload: bool = True

    @field_validator("permissionType")
    @classmethod
    def validate_permission_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in DOCUMENT_PERMISSION_TYPE_VALUES:
            raise ValueError(
                f"permissionType must be one of: {', '.join(DOCUMENT_PERMISSION_TYPE_VALUES)}"
            )
        return value

    @field_validator("roleName")
    @classmethod
    def validate_role_name(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_keys(self) -> "DocumentPermissionIn":
        t = self.permissionType
        if t == "everyone":
            if any([self.roleName, self.buildingId, self.wingId, self.flatId, self.residentId]):
                raise ValueError("everyone permission must not set entity ids or roleName")
        elif t == "role":
            if not self.roleName:
                raise ValueError("role permission requires roleName")
        elif t == "building":
            if not self.buildingId:
                raise ValueError("building permission requires buildingId")
        elif t == "wing":
            if not self.wingId:
                raise ValueError("wing permission requires wingId")
        elif t == "flat":
            if not self.flatId:
                raise ValueError("flat permission requires flatId")
        elif t == "resident":
            if not self.residentId:
                raise ValueError("resident permission requires residentId")
        return self


class DocumentPermissionsReplace(BaseModel):
    permissions: List[DocumentPermissionIn] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    categoryId: Optional[UUID] = None
    fileName: str = Field(..., min_length=1, max_length=255)
    fileUrl: str = Field(..., min_length=1, max_length=500)
    fileSizeBytes: Optional[int] = Field(None, ge=0, le=100 * 1024 * 1024)
    mimeType: Optional[str] = Field(None, max_length=100)
    scope: str = Field(default="society", max_length=32)
    tags: List[str] = Field(default_factory=list)
    folderPath: Optional[str] = Field(None, max_length=500)
    expiresAt: Optional[datetime] = None
    isPinned: bool = False
    isFavoriteDefault: bool = False
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    permissions: List[DocumentPermissionIn] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    @field_validator("description", "notes", "folderPath")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("fileName", "fileUrl")
    @classmethod
    def validate_required_file_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("mimeType")
    @classmethod
    def validate_mime(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value.lower() not in ALLOWED_DOC_MIMES:
            raise ValueError("mimeType is not allowed")
        return value.lower() if value else None

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in DOCUMENT_SCOPE_VALUES:
            raise ValueError(f"scope must be one of: {', '.join(DOCUMENT_SCOPE_VALUES)}")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: List[str]) -> List[str]:
        cleaned = []
        for tag in value:
            t = (tag or "").strip()
            if t:
                cleaned.append(t)
        return cleaned


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    categoryId: Optional[UUID] = None
    fileName: Optional[str] = Field(None, min_length=1, max_length=255)
    fileUrl: Optional[str] = Field(None, min_length=1, max_length=500)
    fileSizeBytes: Optional[int] = Field(None, ge=0, le=100 * 1024 * 1024)
    mimeType: Optional[str] = Field(None, max_length=100)
    scope: Optional[str] = Field(None, max_length=32)
    tags: Optional[List[str]] = None
    folderPath: Optional[str] = Field(None, max_length=500)
    expiresAt: Optional[datetime] = None
    isPinned: Optional[bool] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    @field_validator("description", "notes", "folderPath")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)

    @field_validator("fileName", "fileUrl")
    @classmethod
    def validate_optional_file_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("mimeType")
    @classmethod
    def validate_mime(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _normalize_optional_str(value)
        if value and value.lower() not in ALLOWED_DOC_MIMES:
            raise ValueError("mimeType is not allowed")
        return value.lower() if value else None

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in DOCUMENT_SCOPE_VALUES:
            raise ValueError(f"scope must be one of: {', '.join(DOCUMENT_SCOPE_VALUES)}")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = []
        for tag in value:
            t = (tag or "").strip()
            if t:
                cleaned.append(t)
        return cleaned


class DocumentVersionCreate(BaseModel):
    fileName: str = Field(..., min_length=1, max_length=255)
    fileUrl: str = Field(..., min_length=1, max_length=500)
    fileSizeBytes: Optional[int] = Field(None, ge=0, le=100 * 1024 * 1024)
    mimeType: Optional[str] = Field(None, max_length=100)
    changeNotes: Optional[str] = None

    @field_validator("fileName", "fileUrl")
    @classmethod
    def validate_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("changeNotes")
    @classmethod
    def validate_change_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("mimeType")
    @classmethod
    def validate_mime(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value.lower() not in ALLOWED_DOC_MIMES:
            raise ValueError("mimeType is not allowed")
        return value.lower() if value else None
