"""Pydantic schemas for Visitor identity.

Metadata risk flags (documentation + optional payload keys):
  metadata.blacklisted -> bool
  metadata.vip         -> bool
  metadata.frequent    -> bool

Future documentation only (no implementation/table now):
  - VisitorVehicle relation
  - Gate table
  - Shift relation for guard staffing
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from Schemas.common import ListQueryParams


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class VisitorListQueryParams(ListQueryParams):
    phone: Optional[str] = None
    government_id_type: Optional[str] = Field(None, alias="governmentIdType")

    model_config = {"populate_by_name": True}


class VisitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    photoUrl: Optional[str] = Field(None, max_length=500)
    governmentIdType: Optional[str] = Field(None, max_length=50)
    governmentIdNumber: Optional[str] = Field(None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("name", "phone")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("photoUrl", "governmentIdType", "governmentIdNumber", "notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitorUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    photoUrl: Optional[str] = Field(None, max_length=500)
    governmentIdType: Optional[str] = Field(None, max_length=50)
    governmentIdNumber: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("name", "phone", "photoUrl", "governmentIdType", "governmentIdNumber", "notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitorOut(BaseModel):
    id: UUID
    societyId: UUID
    name: str
    phone: str
    email: Optional[str] = None
    photoUrl: Optional[str] = None
    governmentIdType: Optional[str] = None
    governmentIdNumber: Optional[str] = None
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
    def from_orm_visitor(cls, visitor: Any) -> "VisitorOut":
        return cls(
            id=visitor.id,
            societyId=visitor.society_id,
            name=visitor.name,
            phone=visitor.phone,
            email=visitor.email,
            photoUrl=visitor.photo_url,
            governmentIdType=visitor.government_id_type,
            governmentIdNumber=visitor.government_id_number,
            metadata=visitor.metadata_json or {},
            notes=visitor.notes,
            isActive=visitor.is_active,
            version=visitor.version,
            createdBy=visitor.created_by,
            updatedBy=visitor.updated_by,
            lastActivityAt=visitor.last_activity_at,
            createdAt=visitor.created_at,
            updatedAt=visitor.updated_at,
        )
