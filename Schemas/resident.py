"""Pydantic schemas for Resident module.

Metadata conventions (no dedicated columns):
  metadata.emergency   — e.g. { "name", "phone", "relation" }
  metadata.medical     — e.g. { "bloodGroup", "allergies", "conditions" }
  metadata.preferences — e.g. { "language", "contactMethod" }
  metadata.documents   — e.g. { "idProofRef", "leaseRef" } (URLs until upload service)

Future Household (documentation only — no table):
  A household groups active occupancies on a flat under one billing/notice unit.
  Phase 5 uses flat_id + primary occupancy as implicit household.

Future Occupancy Type vs Resident Role (documentation only):
  - role (owner/tenant/family_member/domestic_help) = person's relationship to the flat
  - occupancy_type (future) = lease type / billing category (e.g. long_term, short_term, company)
  Store future occupancy_type in occupancy.metadata.occupancyType until promoted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from Schemas.common import ListQueryParams


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ResidentListQueryParams(ListQueryParams):
    model_config = {"populate_by_name": True}


class ResidentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, max_length=32)
    dob: Optional[date] = None
    userId: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("phone", "notes", "gender")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ResidentUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, max_length=32)
    dob: Optional[date] = None
    userId: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("name", "phone", "notes", "gender")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ResidentOut(BaseModel):
    id: UUID
    societyId: UUID
    userId: Optional[UUID] = None
    code: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    metadata: Dict[str, Any]
    notes: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime
    currentOccupancies: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_orm_resident(
        cls,
        resident: Any,
        *,
        current_occupancies: Optional[List[Dict[str, Any]]] = None,
    ) -> "ResidentOut":
        return cls(
            id=resident.id,
            societyId=resident.society_id,
            userId=resident.user_id,
            code=resident.code,
            name=resident.name,
            email=resident.email,
            phone=resident.phone,
            gender=resident.gender,
            dob=resident.dob,
            metadata=resident.metadata_json or {},
            notes=resident.notes,
            isActive=resident.is_active,
            version=resident.version,
            createdBy=resident.created_by,
            updatedBy=resident.updated_by,
            lastActivityAt=resident.last_activity_at,
            createdAt=resident.created_at,
            updatedAt=resident.updated_at,
            currentOccupancies=current_occupancies or [],
        )
