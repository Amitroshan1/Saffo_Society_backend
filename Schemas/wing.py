"""Pydantic schemas for Wing module."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

WING_CODE_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,31}$")
WING_STATUS_VALUES = ("operational", "under_maintenance", "blocked")
WING_TYPE_VALUES = ("residential", "commercial", "service", "mixed")
COLOR_REGEX = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

# capacity: maximum flat/unit slots this wing can hold (not persons).
# Use metadata for alternate semantics if a society configures differently.


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class WingListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")

    model_config = {"populate_by_name": True}


class WingCreate(BaseModel):
    buildingId: UUID
    name: str = Field(..., min_length=1, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    code: str = Field(..., min_length=1, max_length=32)
    shortCode: Optional[str] = Field(None, max_length=16)
    description: Optional[str] = None
    wingType: Optional[str] = Field(None, max_length=50)
    status: str = Field(default="operational", max_length=32)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sequence: int = Field(default=0, ge=0, le=9999)
    color: Optional[str] = Field(None, max_length=7)
    totalFloors: Optional[int] = Field(None, ge=0, le=200)
    totalFlats: Optional[int] = Field(None, ge=0, le=100000)
    elevatorCount: Optional[int] = Field(None, ge=0, le=100)
    emergencyStairCount: Optional[int] = Field(None, ge=0, le=100)
    capacity: Optional[int] = Field(
        None,
        ge=0,
        le=100000,
        description="Max flat/unit slots in this wing (not headcount)",
    )
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("displayName", "description", "notes", "shortCode")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("wingType")
    @classmethod
    def validate_wing_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value not in WING_TYPE_VALUES:
            raise ValueError(f"wingType must be one of: {', '.join(WING_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in WING_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(WING_STATUS_VALUES)}")
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not WING_CODE_REGEX.fullmatch(normalized):
            raise ValueError("code must be 1-32 chars: A-Z, 0-9, underscore, hyphen")
        return normalized

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and not COLOR_REGEX.fullmatch(value):
            raise ValueError("color must be a hex value like #RGB or #RRGGBB")
        return value.upper() if value else value


class WingUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    shortCode: Optional[str] = Field(None, max_length=16)
    description: Optional[str] = None
    wingType: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=32)
    metadata: Optional[Dict[str, Any]] = None
    sequence: Optional[int] = Field(None, ge=0, le=9999)
    color: Optional[str] = Field(None, max_length=7)
    totalFloors: Optional[int] = Field(None, ge=0, le=200)
    totalFlats: Optional[int] = Field(None, ge=0, le=100000)
    elevatorCount: Optional[int] = Field(None, ge=0, le=100)
    emergencyStairCount: Optional[int] = Field(None, ge=0, le=100)
    capacity: Optional[int] = Field(None, ge=0, le=100000)
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("displayName", "description", "notes", "shortCode")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("wingType")
    @classmethod
    def validate_wing_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value not in WING_TYPE_VALUES:
            raise ValueError(f"wingType must be one of: {', '.join(WING_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in WING_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(WING_STATUS_VALUES)}")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and not COLOR_REGEX.fullmatch(value):
            raise ValueError("color must be a hex value like #RGB or #RRGGBB")
        return value.upper() if value else value


class WingOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    buildingName: Optional[str] = None
    buildingCode: Optional[str] = None
    name: str
    displayName: Optional[str] = None
    code: str
    shortCode: Optional[str] = None
    description: Optional[str] = None
    wingType: Optional[str] = None
    status: str
    metadata: Dict[str, Any]
    sequence: int
    color: Optional[str] = None
    totalFloors: Optional[int] = None
    totalFlats: Optional[int] = None
    elevatorCount: Optional[int] = None
    emergencyStairCount: Optional[int] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_wing(
        cls,
        wing: Any,
        *,
        building_name: Optional[str] = None,
        building_code: Optional[str] = None,
    ) -> "WingOut":
        return cls(
            id=wing.id,
            societyId=wing.society_id,
            buildingId=wing.building_id,
            buildingName=building_name,
            buildingCode=building_code,
            name=wing.name,
            displayName=wing.display_name,
            code=wing.code,
            shortCode=wing.short_code,
            description=wing.description,
            wingType=wing.wing_type,
            status=wing.status,
            metadata=wing.metadata_json or {},
            sequence=wing.sequence,
            color=wing.color,
            totalFloors=wing.total_floors,
            totalFlats=wing.total_flats,
            elevatorCount=wing.elevator_count,
            emergencyStairCount=wing.emergency_stair_count,
            capacity=wing.capacity,
            notes=wing.notes,
            isActive=wing.is_active,
            version=wing.version,
            createdBy=wing.created_by,
            updatedBy=wing.updated_by,
            lastActivityAt=wing.last_activity_at,
            createdAt=wing.created_at,
            updatedAt=wing.updated_at,
        )
