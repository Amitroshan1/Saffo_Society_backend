"""Pydantic schemas for Building module."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BUILDING_CODE_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,31}$")
BUILDING_STATUS_VALUES = ("operational", "under_maintenance", "blocked")
BUILDING_TYPE_VALUES = ("tower", "block", "villa", "commercial", "mixed")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_units(planned: Optional[int], occupied: Optional[int], vacant: Optional[int]) -> None:
    if occupied is not None and occupied < 0:
        raise ValueError("occupiedUnits must be >= 0")
    if vacant is not None and vacant < 0:
        raise ValueError("vacantUnits must be >= 0")
    if planned is not None and planned < 0:
        raise ValueError("plannedUnits must be >= 0")
    if planned is not None and occupied is not None and occupied > planned:
        raise ValueError("occupiedUnits cannot be greater than plannedUnits")
    if planned is not None and vacant is not None and vacant > planned:
        raise ValueError("vacantUnits cannot be greater than plannedUnits")
    if (
        planned is not None
        and occupied is not None
        and vacant is not None
        and occupied + vacant > planned
    ):
        raise ValueError("occupiedUnits + vacantUnits cannot exceed plannedUnits")


class BuildingCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    code: str = Field(..., min_length=1, max_length=32)
    description: Optional[str] = None
    buildingType: Optional[str] = Field(None, max_length=50)
    status: str = Field(default="operational", max_length=32)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    addressLine1: Optional[str] = Field(None, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    emergencyContactName: Optional[str] = Field(None, max_length=120)
    emergencyContactPhone: Optional[str] = Field(None, max_length=20)
    totalFloors: Optional[int] = Field(None, ge=0, le=200)
    totalUnits: Optional[int] = Field(None, ge=0, le=100000)
    plannedUnits: Optional[int] = Field(None, ge=0, le=100000)
    occupiedUnits: Optional[int] = Field(None, ge=0, le=100000)
    vacantUnits: Optional[int] = Field(None, ge=0, le=100000)
    builtYear: Optional[int] = None
    hasLift: bool = False
    hasParking: bool = False
    imageUrl: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("displayName", "description", "addressLine1", "addressLine2", "notes")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("emergencyContactName", "emergencyContactPhone", "imageUrl")
    @classmethod
    def strip_nullable_fields(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("buildingType")
    @classmethod
    def validate_building_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value not in BUILDING_TYPE_VALUES:
            raise ValueError(f"buildingType must be one of: {', '.join(BUILDING_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in BUILDING_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(BUILDING_STATUS_VALUES)}")
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not BUILDING_CODE_REGEX.fullmatch(normalized):
            raise ValueError("code must be 1-32 chars: A-Z, 0-9, underscore, hyphen")
        return normalized

    @field_validator("builtYear")
    @classmethod
    def validate_year(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        max_year = datetime.now().year + 1
        if value < 1900 or value > max_year:
            raise ValueError(f"builtYear must be between 1900 and {max_year}")
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> "BuildingCreate":
        _validate_units(self.plannedUnits, self.occupiedUnits, self.vacantUnits)
        return self


class BuildingUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    buildingType: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=32)
    metadata: Optional[Dict[str, Any]] = None
    addressLine1: Optional[str] = Field(None, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    emergencyContactName: Optional[str] = Field(None, max_length=120)
    emergencyContactPhone: Optional[str] = Field(None, max_length=20)
    totalFloors: Optional[int] = Field(None, ge=0, le=200)
    totalUnits: Optional[int] = Field(None, ge=0, le=100000)
    plannedUnits: Optional[int] = Field(None, ge=0, le=100000)
    occupiedUnits: Optional[int] = Field(None, ge=0, le=100000)
    vacantUnits: Optional[int] = Field(None, ge=0, le=100000)
    builtYear: Optional[int] = None
    hasLift: Optional[bool] = None
    hasParking: Optional[bool] = None
    imageUrl: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("displayName", "description", "addressLine1", "addressLine2", "notes")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("emergencyContactName", "emergencyContactPhone", "imageUrl")
    @classmethod
    def strip_nullable_fields(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("buildingType")
    @classmethod
    def validate_building_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and value not in BUILDING_TYPE_VALUES:
            raise ValueError(f"buildingType must be one of: {', '.join(BUILDING_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in BUILDING_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(BUILDING_STATUS_VALUES)}")
        return value

    @field_validator("builtYear")
    @classmethod
    def validate_year(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        max_year = datetime.now().year + 1
        if value < 1900 or value > max_year:
            raise ValueError(f"builtYear must be between 1900 and {max_year}")
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> "BuildingUpdate":
        _validate_units(self.plannedUnits, self.occupiedUnits, self.vacantUnits)
        return self


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    societyId: UUID
    name: str
    displayName: Optional[str] = None
    code: str
    description: Optional[str] = None
    buildingType: Optional[str] = None
    status: str
    metadata: Dict[str, Any]
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    emergencyContactName: Optional[str] = None
    emergencyContactPhone: Optional[str] = None
    totalFloors: Optional[int] = None
    totalUnits: Optional[int] = None
    plannedUnits: Optional[int] = None
    occupiedUnits: Optional[int] = None
    vacantUnits: Optional[int] = None
    builtYear: Optional[int] = None
    hasLift: bool
    hasParking: bool
    imageUrl: Optional[str] = None
    notes: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_building(cls, building: Any) -> "BuildingOut":
        return cls(
            id=building.id,
            societyId=building.society_id,
            name=building.name,
            displayName=building.display_name,
            code=building.code,
            description=building.description,
            buildingType=building.building_type,
            status=building.status,
            metadata=building.metadata_json or {},
            addressLine1=building.address_line1,
            addressLine2=building.address_line2,
            emergencyContactName=building.emergency_contact_name,
            emergencyContactPhone=building.emergency_contact_phone,
            totalFloors=building.total_floors,
            totalUnits=building.total_units,
            plannedUnits=building.planned_units,
            occupiedUnits=building.occupied_units,
            vacantUnits=building.vacant_units,
            builtYear=building.built_year,
            hasLift=building.has_lift,
            hasParking=building.has_parking,
            imageUrl=building.image_url,
            notes=building.notes,
            isActive=building.is_active,
            version=building.version,
            createdBy=building.created_by,
            updatedBy=building.updated_by,
            lastActivityAt=building.last_activity_at,
            createdAt=building.created_at,
            updatedAt=building.updated_at,
        )
