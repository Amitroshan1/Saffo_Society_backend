"""Pydantic schemas for Notices & Announcements (Phase 11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Schemas.common import ListQueryParams
from Schemas.resident_notice_schema import ResidentNoticeListQueryParams

NOTICE_CATEGORY_VALUES = (
    "general",
    "maintenance",
    "emergency",
    "events",
    "committee",
    "security",
    "water",
    "electricity",
    "parking",
    "festival",
    "finance",
    "other",
)
NOTICE_PRIORITY_VALUES = ("low", "normal", "high", "critical")
NOTICE_STATUS_VALUES = (
    "draft",
    "scheduled",
    "published",
    "expired",
    "archived",
    "cancelled",
)
NOTICE_TARGET_TYPE_VALUES = (
    "society",
    "building",
    "wing",
    "flat",
    "resident",
    "committee_role",
)

ALLOWED_ATTACHMENT_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}


def _norm_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class NoticeListQueryParams(ListQueryParams):
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    is_pinned: Optional[bool] = Field(None, alias="isPinned")
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    from_date: Optional[datetime] = Field(None, alias="from")
    to_date: Optional[datetime] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


class NoticeTargetIn(BaseModel):
    targetType: str = Field(..., max_length=32)
    buildingId: Optional[UUID] = None
    wingId: Optional[UUID] = None
    flatId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    committeeRole: Optional[str] = Field(None, max_length=64)

    @field_validator("targetType")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in NOTICE_TARGET_TYPE_VALUES:
            raise ValueError(
                f"targetType must be one of: {', '.join(NOTICE_TARGET_TYPE_VALUES)}"
            )
        return value

    @field_validator("committeeRole")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_keys(self) -> "NoticeTargetIn":
        t = self.targetType
        if t == "society":
            if any([self.buildingId, self.wingId, self.flatId, self.residentId, self.committeeRole]):
                raise ValueError("society target must not set entity ids")
        elif t == "building":
            if not self.buildingId:
                raise ValueError("building target requires buildingId")
        elif t == "wing":
            if not self.wingId:
                raise ValueError("wing target requires wingId")
        elif t == "flat":
            if not self.flatId:
                raise ValueError("flat target requires flatId")
        elif t == "resident":
            if not self.residentId:
                raise ValueError("resident target requires residentId")
        elif t == "committee_role":
            if not self.committeeRole:
                raise ValueError("committee_role target requires committeeRole")
        return self


class NoticeAttachmentIn(BaseModel):
    fileName: str = Field(..., min_length=1, max_length=255)
    fileUrl: str = Field(..., min_length=1, max_length=500)
    mimeType: Optional[str] = Field(None, max_length=100)
    fileSizeBytes: Optional[int] = Field(None, ge=0, le=10 * 1024 * 1024)
    sortOrder: int = Field(default=0, ge=0)

    @field_validator("fileName", "fileUrl")
    @classmethod
    def validate_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("mimeType")
    @classmethod
    def validate_mime(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value.lower() not in ALLOWED_ATTACHMENT_MIMES:
            raise ValueError("mimeType is not allowed")
        return value.lower() if value else None


class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: Optional[str] = Field(None, max_length=500)
    bodyText: str = Field(default="", max_length=50000)
    bodyHtml: Optional[str] = None
    category: str = Field(default="general", max_length=32)
    priority: str = Field(default="normal", max_length=16)
    publishAt: Optional[datetime] = None
    expiresAt: Optional[datetime] = None
    isPinned: bool = False
    pinUntil: Optional[datetime] = None
    requiresAcknowledgement: bool = False
    acknowledgementDueAt: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    targets: List[NoticeTargetIn] = Field(default_factory=list)
    attachments: List[NoticeAttachmentIn] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be blank")
        return value

    @field_validator("summary", "notes", "bodyHtml")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("bodyText")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return value.strip() if value else ""

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in NOTICE_CATEGORY_VALUES:
            raise ValueError(f"category must be one of: {', '.join(NOTICE_CATEGORY_VALUES)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in NOTICE_PRIORITY_VALUES:
            raise ValueError(f"priority must be one of: {', '.join(NOTICE_PRIORITY_VALUES)}")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "NoticeCreate":
        if self.publishAt and self.expiresAt and self.expiresAt <= self.publishAt:
            raise ValueError("expiresAt must be after publishAt")
        return self


class NoticeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    summary: Optional[str] = Field(None, max_length=500)
    bodyText: Optional[str] = Field(None, max_length=50000)
    bodyHtml: Optional[str] = None
    category: Optional[str] = Field(None, max_length=32)
    priority: Optional[str] = Field(None, max_length=16)
    publishAt: Optional[datetime] = None
    expiresAt: Optional[datetime] = None
    isPinned: Optional[bool] = None
    pinUntil: Optional[datetime] = None
    requiresAcknowledgement: Optional[bool] = None
    acknowledgementDueAt: Optional[datetime] = None
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

    @field_validator("summary", "notes", "bodyHtml", "bodyText")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip()

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in NOTICE_CATEGORY_VALUES:
            raise ValueError(f"category must be one of: {', '.join(NOTICE_CATEGORY_VALUES)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in NOTICE_PRIORITY_VALUES:
            raise ValueError(f"priority must be one of: {', '.join(NOTICE_PRIORITY_VALUES)}")
        return value


class NoticeTargetsReplace(BaseModel):
    targets: List[NoticeTargetIn] = Field(..., min_length=1)


class NoticeCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class NoticePinRequest(BaseModel):
    pinUntil: Optional[datetime] = None
