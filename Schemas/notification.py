"""Pydantic schemas for Notifications & Communication (Phase 15)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Schemas.common import ListQueryParams

TEMPLATE_CATEGORIES = (
    "system",
    "billing",
    "complaint",
    "visitor",
    "notice",
    "document",
    "amenity",
    "parking",
    "auth",
    "emergency",
    "marketing",
    "other",
)
CHANNELS = ("in_app", "email", "sms", "push", "webhook")
PRIORITIES = ("low", "normal", "high", "critical")
SOURCE_MODULES = (
    "auth",
    "complaints",
    "billing",
    "payments",
    "visitors",
    "staff",
    "notices",
    "documents",
    "amenities",
    "parking",
    "system",
    "emergency",
    "other",
)
TARGET_TYPES = ("society", "building", "wing", "flat", "resident", "role", "user")
NOTIFICATION_STATUSES = (
    "pending",
    "queued",
    "sending",
    "delivered",
    "read",
    "failed",
    "cancelled",
    "archived",
)
DELIVERY_STATUSES = ("queued", "sending", "delivered", "failed", "cancelled")
SCHEDULE_STATUSES = ("scheduled", "processing", "completed", "cancelled", "failed")
RECURRENCES = ("none", "daily", "weekly", "monthly")

KNOWN_PLACEHOLDERS = (
    "resident_name",
    "society_name",
    "building",
    "wing",
    "flat",
    "amount",
    "invoice_number",
    "visitor_name",
    "booking_number",
    "parking_slot",
    "document_name",
    "notice_title",
    "complaint_title",
    "shift_type",
    "shift_date",
    "purpose",
)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _norm_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def validate_placeholders(template: str) -> str:
    unknown = sorted(
        {m.group(1) for m in PLACEHOLDER_RE.finditer(template)} - set(KNOWN_PLACEHOLDERS)
    )
    if unknown:
        raise ValueError(f"Unknown placeholders: {', '.join(unknown)}")
    return template


def validate_channels(channels: List[str]) -> List[str]:
    if not channels:
        raise ValueError("At least one channel is required")
    normalized = []
    for ch in channels:
        value = _norm_enum(ch)
        if value not in CHANNELS:
            raise ValueError(f"channel must be one of: {', '.join(CHANNELS)}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def render_template(template_str: str, variables: Dict[str, Any] | None = None) -> str:
    """Replace {{placeholder}} tokens using provided variables."""
    variables = variables or {}

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key)
        if value is None:
            return ""
        return str(value)

    return PLACEHOLDER_RE.sub(_replace, template_str)


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


class TemplateListQueryParams(ListQueryParams):
    category: Optional[str] = None
    channel: Optional[str] = None

    model_config = {"populate_by_name": True}


class NotificationListQueryParams(ListQueryParams):
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    source_module: Optional[str] = Field(None, alias="sourceModule")
    user_id: Optional[UUID] = Field(None, alias="userId")
    resident_id: Optional[UUID] = Field(None, alias="residentId")

    model_config = {"populate_by_name": True}


class DeliveryListQueryParams(ListQueryParams):
    status: Optional[str] = None
    channel: Optional[str] = None
    notification_id: Optional[UUID] = Field(None, alias="notificationId")

    model_config = {"populate_by_name": True}


class ScheduledListQueryParams(ListQueryParams):
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class NotificationTemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., max_length=64)
    channel: str = Field(..., max_length=32)
    subjectTemplate: Optional[str] = Field(None, max_length=500)
    bodyTemplate: str = Field(..., min_length=1)
    priority: str = Field(default="normal", max_length=16)
    isSystem: bool = False
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
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

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in TEMPLATE_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(TEMPLATE_CATEGORIES)}")
        return value

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in CHANNELS:
            raise ValueError(f"channel must be one of: {', '.join(CHANNELS)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of: {', '.join(PRIORITIES)}")
        return value

    @field_validator("bodyTemplate")
    @classmethod
    def validate_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("bodyTemplate cannot be blank")
        return validate_placeholders(value)

    @field_validator("subjectTemplate")
    @classmethod
    def validate_subject(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value is None:
            return None
        return validate_placeholders(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class NotificationTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=64)
    channel: Optional[str] = Field(None, max_length=32)
    subjectTemplate: Optional[str] = Field(None, max_length=500)
    bodyTemplate: Optional[str] = Field(None, min_length=1)
    priority: Optional[str] = Field(None, max_length=16)
    isSystem: Optional[bool] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    isActive: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in TEMPLATE_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(TEMPLATE_CATEGORIES)}")
        return value

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in CHANNELS:
            raise ValueError(f"channel must be one of: {', '.join(CHANNELS)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of: {', '.join(PRIORITIES)}")
        return value

    @field_validator("bodyTemplate")
    @classmethod
    def validate_body(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("bodyTemplate cannot be blank")
        return validate_placeholders(value)

    @field_validator("subjectTemplate")
    @classmethod
    def validate_subject(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _normalize_optional_str(value)
        if value is None:
            return None
        return validate_placeholders(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Broadcast / schedule
# ---------------------------------------------------------------------------


class BroadcastRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    body: Optional[str] = None
    templateCode: Optional[str] = Field(None, max_length=64)
    templateId: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app"])
    category: str = Field(default="system", max_length=64)
    priority: str = Field(default="normal", max_length=16)
    targetType: str = Field(..., max_length=32)
    targetRole: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    wingId: Optional[UUID] = None
    flatId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    userId: Optional[UUID] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def validate_channels_field(cls, value: List[str]) -> List[str]:
        return validate_channels(value)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in TEMPLATE_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(TEMPLATE_CATEGORIES)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of: {', '.join(PRIORITIES)}")
        return value

    @field_validator("targetType")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in TARGET_TYPES:
            raise ValueError(f"targetType must be one of: {', '.join(TARGET_TYPES)}")
        return value

    @field_validator("targetRole", "templateCode", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_content_and_target(self) -> "BroadcastRequest":
        has_template = bool(self.templateCode or self.templateId)
        has_content = bool((self.title and self.title.strip()) and (self.body and self.body.strip()))
        if not has_template and not has_content:
            raise ValueError("Provide templateCode/templateId or title+body")
        if self.targetType == "role" and not self.targetRole:
            raise ValueError("targetRole is required when targetType is role")
        if self.targetType == "building" and not self.buildingId:
            raise ValueError("buildingId is required when targetType is building")
        if self.targetType == "wing" and not self.wingId:
            raise ValueError("wingId is required when targetType is wing")
        if self.targetType == "flat" and not self.flatId:
            raise ValueError("flatId is required when targetType is flat")
        if self.targetType == "resident" and not self.residentId:
            raise ValueError("residentId is required when targetType is resident")
        if self.targetType == "user" and not self.userId:
            raise ValueError("userId is required when targetType is user")
        return self


class ScheduleNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    templateId: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app"])
    targetType: str = Field(..., max_length=32)
    targetRole: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    wingId: Optional[UUID] = None
    flatId: Optional[UUID] = None
    residentIds: List[UUID] = Field(default_factory=list)
    priority: str = Field(default="normal", max_length=16)
    category: str = Field(default="system", max_length=64)
    scheduleAt: datetime
    recurrence: Optional[str] = Field(None, max_length=32)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "body")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("cannot be blank")
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels_field(cls, value: List[str]) -> List[str]:
        return validate_channels(value)

    @field_validator("targetType")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in TARGET_TYPES:
            raise ValueError(f"targetType must be one of: {', '.join(TARGET_TYPES)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of: {', '.join(PRIORITIES)}")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in TEMPLATE_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(TEMPLATE_CATEGORIES)}")
        return value

    @field_validator("recurrence")
    @classmethod
    def validate_recurrence(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in RECURRENCES:
            raise ValueError(f"recurrence must be one of: {', '.join(RECURRENCES)}")
        return value

    @field_validator("targetRole", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Preferences / finance
# ---------------------------------------------------------------------------


class PreferenceUpdate(BaseModel):
    emailEnabled: Optional[bool] = None
    smsEnabled: Optional[bool] = None
    pushEnabled: Optional[bool] = None
    marketingEnabled: Optional[bool] = None
    systemEnabled: Optional[bool] = None
    emergencyEnabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentReminderRequest(BaseModel):
    residentId: UUID
    amount: Optional[str] = None
    invoiceNumber: Optional[str] = None
    billId: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app", "email"])
    variables: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def validate_channels_field(cls, value: List[str]) -> List[str]:
        return validate_channels(value)


class InvoiceNotificationRequest(BaseModel):
    residentId: UUID
    invoiceNumber: Optional[str] = None
    amount: Optional[str] = None
    billId: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app", "email"])
    variables: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def validate_channels_field(cls, value: List[str]) -> List[str]:
        return validate_channels(value)


class ReceiptNotificationRequest(BaseModel):
    residentId: UUID
    amount: Optional[str] = None
    receiptNumber: Optional[str] = None
    paymentId: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app", "email"])
    variables: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def validate_channels_field(cls, value: List[str]) -> List[str]:
        return validate_channels(value)
