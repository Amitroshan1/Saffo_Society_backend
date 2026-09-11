"""Pydantic schemas for Complaint module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

COMPLAINT_PRIORITY_VALUES = ("low", "medium", "high", "critical")
COMPLAINT_STATUS_VALUES = (
    "open",
    "assigned",
    "in_progress",
    "waiting",
    "resolved",
    "closed",
    "reopened",
    "rejected",
)
COMPLAINT_CATEGORY_VALUES = (
    "electrical",
    "plumbing",
    "housekeeping",
    "security",
    "parking",
    "lift",
    "water",
    "internet",
    "common_area",
    "other",
)
COMPLAINT_SOURCE_VALUES = ("resident", "admin", "guard", "staff", "system")
AUTHOR_TYPE_VALUES = ("resident", "admin", "staff", "guard")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ComplaintListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    wing_id: Optional[UUID] = Field(None, alias="wingId")
    flat_id: Optional[UUID] = Field(None, alias="flatId")
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    assigned_staff_id: Optional[UUID] = Field(None, alias="assignedStaffId")
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class ComplaintAttachmentIn(BaseModel):
    fileName: str = Field(..., min_length=1, max_length=255)
    fileUrl: str = Field(..., min_length=1, max_length=500)
    mimeType: Optional[str] = Field(None, max_length=100)

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
        return _normalize_optional_str(value)


class ComplaintCreate(BaseModel):
    occupancyId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    flatId: Optional[UUID] = None
    category: str = Field(..., max_length=64)
    subcategory: Optional[str] = Field(None, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: str = Field(default="medium", max_length=32)
    source: str = Field(default="resident", max_length=32)
    expectedResolution: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[ComplaintAttachmentIn] = Field(default_factory=list)

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        if value not in COMPLAINT_CATEGORY_VALUES:
            raise ValueError(f"category must be one of: {', '.join(COMPLAINT_CATEGORY_VALUES)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in COMPLAINT_PRIORITY_VALUES:
            raise ValueError(f"priority must be one of: {', '.join(COMPLAINT_PRIORITY_VALUES)}")
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in COMPLAINT_SOURCE_VALUES:
            raise ValueError(f"source must be one of: {', '.join(COMPLAINT_SOURCE_VALUES)}")
        return value

    @field_validator("subcategory", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ComplaintUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Optional[str] = Field(None, max_length=64)
    subcategory: Optional[str] = Field(None, max_length=64)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    expectedResolution: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        if value not in COMPLAINT_CATEGORY_VALUES:
            raise ValueError(f"category must be one of: {', '.join(COMPLAINT_CATEGORY_VALUES)}")
        return value

    @field_validator("title", "description", "subcategory", "notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ComplaintAssign(BaseModel):
    staffId: UUID
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ComplaintStatusUpdate(BaseModel):
    status: str = Field(..., max_length=32)
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        if value not in COMPLAINT_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(COMPLAINT_STATUS_VALUES)}")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ComplaintPriorityUpdate(BaseModel):
    priority: str = Field(..., max_length=32)
    notes: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in COMPLAINT_PRIORITY_VALUES:
            raise ValueError(f"priority must be one of: {', '.join(COMPLAINT_PRIORITY_VALUES)}")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ComplaintCommentCreate(BaseModel):
    message: str = Field(..., min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be blank")
        return value


class ComplaintCommentOut(BaseModel):
    id: UUID
    complaintId: UUID
    authorType: str
    authorId: UUID
    authorName: Optional[str] = None
    message: str
    createdAt: datetime
    createdBy: Optional[UUID] = None


class ComplaintAttachmentOut(BaseModel):
    id: UUID
    complaintId: UUID
    fileName: str
    fileUrl: str
    mimeType: Optional[str] = None
    uploadedBy: Optional[UUID] = None
    createdAt: datetime


class ComplaintOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    wingId: UUID
    flatId: UUID
    occupancyId: UUID
    residentId: UUID
    assignedStaffId: Optional[UUID] = None
    category: str
    subcategory: Optional[str] = None
    title: str
    description: str
    priority: str
    status: str
    source: str
    expectedResolution: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None
    closedAt: Optional[datetime] = None
    metadata: Dict[str, Any]
    notes: Optional[str] = None
    residentName: Optional[str] = None
    residentCode: Optional[str] = None
    flatNo: Optional[str] = None
    wingCode: Optional[str] = None
    buildingName: Optional[str] = None
    assignedStaffName: Optional[str] = None
    comments: Optional[List[ComplaintCommentOut]] = None
    attachments: Optional[List[ComplaintAttachmentOut]] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_complaint(
        cls,
        complaint: Any,
        *,
        resident_name: Optional[str] = None,
        resident_code: Optional[str] = None,
        flat_no: Optional[str] = None,
        wing_code: Optional[str] = None,
        building_name: Optional[str] = None,
        assigned_staff_name: Optional[str] = None,
        comments: Optional[List[ComplaintCommentOut]] = None,
        attachments: Optional[List[ComplaintAttachmentOut]] = None,
    ) -> "ComplaintOut":
        return cls(
            id=complaint.id,
            societyId=complaint.society_id,
            buildingId=complaint.building_id,
            wingId=complaint.wing_id,
            flatId=complaint.flat_id,
            occupancyId=complaint.occupancy_id,
            residentId=complaint.resident_id,
            assignedStaffId=complaint.assigned_staff_id,
            category=complaint.category,
            subcategory=complaint.subcategory,
            title=complaint.title,
            description=complaint.description,
            priority=complaint.priority,
            status=complaint.status,
            source=complaint.source,
            expectedResolution=complaint.expected_resolution,
            resolvedAt=complaint.resolved_at,
            closedAt=complaint.closed_at,
            metadata=complaint.metadata_json or {},
            notes=complaint.notes,
            residentName=resident_name,
            residentCode=resident_code,
            flatNo=flat_no,
            wingCode=wing_code,
            buildingName=building_name,
            assignedStaffName=assigned_staff_name,
            comments=comments,
            attachments=attachments,
            isActive=complaint.is_active,
            version=complaint.version,
            createdBy=complaint.created_by,
            updatedBy=complaint.updated_by,
            lastActivityAt=complaint.last_activity_at,
            createdAt=complaint.created_at,
            updatedAt=complaint.updated_at,
        )
