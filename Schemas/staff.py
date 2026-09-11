"""Pydantic schemas for Staff module.

Metadata conventions (no dedicated columns):
  metadata.emergency       — { name, phone, relation }
  metadata.certifications  — e.g. { fireSafety, firstAid }
  metadata.agency          — { name, contractRef }
  metadata.accessLevel     — string
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from Schemas.common import ListQueryParams

STAFF_ROLE_VALUES = (
    "security_guard",
    "security_supervisor",
    "housekeeping",
    "facility_manager",
    "electrician",
    "plumber",
    "gardener",
    "receptionist",
    "other",
)

EMPLOYMENT_TYPE_VALUES = ("permanent", "contract", "agency")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class StaffListQueryParams(ListQueryParams):
    staff_role: Optional[str] = Field(None, alias="staffRole")
    employment_type: Optional[str] = Field(None, alias="employmentType")
    assigned_gate_id: Optional[UUID] = Field(None, alias="assignedGateId")
    assigned_building_id: Optional[UUID] = Field(None, alias="assignedBuildingId")

    model_config = {"populate_by_name": True}


class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=20)
    staffRole: str = Field(..., max_length=32)
    email: Optional[EmailStr] = None
    photoUrl: Optional[str] = Field(None, max_length=500)
    department: Optional[str] = Field(None, max_length=64)
    employmentType: Optional[str] = Field(None, max_length=32)
    userId: Optional[UUID] = None
    assignedBuildingId: Optional[UUID] = None
    assignedGateId: Optional[UUID] = None
    joiningDate: Optional[date] = None
    leavingDate: Optional[date] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("name", "phone")
    @classmethod
    def validate_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("staffRole")
    @classmethod
    def validate_role(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in STAFF_ROLE_VALUES:
            raise ValueError(f"staffRole must be one of: {', '.join(STAFF_ROLE_VALUES)}")
        return value

    @field_validator("employmentType")
    @classmethod
    def validate_employment(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if not value:
            return None
        value = value.lower()
        if value not in EMPLOYMENT_TYPE_VALUES:
            raise ValueError(f"employmentType must be one of: {', '.join(EMPLOYMENT_TYPE_VALUES)}")
        return value

    @field_validator("photoUrl", "department", "notes")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    staffRole: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    photoUrl: Optional[str] = Field(None, max_length=500)
    department: Optional[str] = Field(None, max_length=64)
    employmentType: Optional[str] = Field(None, max_length=32)
    userId: Optional[UUID] = None
    assignedBuildingId: Optional[UUID] = None
    assignedGateId: Optional[UUID] = None
    joiningDate: Optional[date] = None
    leavingDate: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("name", "phone", "photoUrl", "department", "notes")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("staffRole")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in STAFF_ROLE_VALUES:
            raise ValueError(f"staffRole must be one of: {', '.join(STAFF_ROLE_VALUES)}")
        return value

    @field_validator("employmentType")
    @classmethod
    def validate_employment(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if not value:
            return None
        value = value.lower()
        if value not in EMPLOYMENT_TYPE_VALUES:
            raise ValueError(f"employmentType must be one of: {', '.join(EMPLOYMENT_TYPE_VALUES)}")
        return value


class StaffOut(BaseModel):
    id: UUID
    societyId: UUID
    userId: Optional[UUID] = None
    code: str
    name: str
    phone: str
    email: Optional[str] = None
    photoUrl: Optional[str] = None
    staffRole: str
    department: Optional[str] = None
    employmentType: Optional[str] = None
    assignedBuildingId: Optional[UUID] = None
    assignedBuildingName: Optional[str] = None
    assignedGateId: Optional[UUID] = None
    assignedGateName: Optional[str] = None
    joiningDate: Optional[date] = None
    leavingDate: Optional[date] = None
    metadata: Dict[str, Any]
    notes: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_staff(
        cls,
        staff: Any,
        *,
        building_name: Optional[str] = None,
        gate_name: Optional[str] = None,
    ) -> "StaffOut":
        return cls(
            id=staff.id,
            societyId=staff.society_id,
            userId=staff.user_id,
            code=staff.code,
            name=staff.name,
            phone=staff.phone,
            email=staff.email,
            photoUrl=staff.photo_url,
            staffRole=staff.staff_role,
            department=staff.department,
            employmentType=staff.employment_type,
            assignedBuildingId=staff.assigned_building_id,
            assignedBuildingName=building_name,
            assignedGateId=staff.assigned_gate_id,
            assignedGateName=gate_name,
            joiningDate=staff.joining_date,
            leavingDate=staff.leaving_date,
            metadata=staff.metadata_json or {},
            notes=staff.notes,
            isActive=staff.is_active,
            version=staff.version,
            createdBy=staff.created_by,
            updatedBy=staff.updated_by,
            lastActivityAt=staff.last_activity_at,
            createdAt=staff.created_at,
            updatedAt=staff.updated_at,
        )
