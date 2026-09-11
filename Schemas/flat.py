"""Pydantic schemas for Flat module.

Metadata conventions (do not create dedicated columns for these):
  metadata.utilities — optional object, e.g.
    { "electricityMeter": "...", "waterMeter": "...", "gasConnection": "..." }

Future QR identifier (documentation only — not implemented):
  A dedicated column or metadata key such as `qrCode` / `qr_identifier` may be
  added later for visitor/gate scanning. Do not invent a column in Phase 4.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

FLAT_NO_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,49}$")
COLOR_REGEX = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

FLAT_TYPE_VALUES = (
    "1bhk",
    "2bhk",
    "3bhk",
    "4bhk",
    "studio",
    "penthouse",
    "duplex",
    "shop",
    "office",
    "other",
)
USAGE_TYPE_VALUES = ("residential", "commercial", "office", "shop", "warehouse")
FLAT_STATUS_VALUES = ("vacant", "occupied", "reserved", "under_maintenance", "blocked")
OWNERSHIP_TYPE_VALUES = ("owned", "rented", "company_leased", "vacant")
AREA_TYPE_VALUES = ("carpet", "built_up", "super_built_up")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class FlatListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    wing_id: Optional[UUID] = Field(None, alias="wingId")
    floor_no: Optional[str] = Field(None, alias="floorNo")

    model_config = {"populate_by_name": True}


class FlatCreate(BaseModel):
    wingId: UUID
    flatNo: str = Field(..., min_length=1, max_length=50)
    floorNo: str = Field(..., min_length=1, max_length=20)
    flatType: Optional[str] = Field(None, max_length=50)
    usageType: Optional[str] = Field(None, max_length=50)
    status: str = Field(default="vacant", max_length=32)
    ownershipType: Optional[str] = Field(None, max_length=32)
    areaSqft: Optional[float] = Field(None, ge=0, le=1_000_000)
    areaType: Optional[str] = Field(None, max_length=20)
    intercom: Optional[str] = Field(None, max_length=20)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sequence: int = Field(default=0, ge=0, le=9999)
    color: Optional[str] = Field(None, max_length=7)
    notes: Optional[str] = None

    @field_validator("flatNo")
    @classmethod
    def validate_flat_no(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not FLAT_NO_REGEX.fullmatch(normalized):
            raise ValueError("flatNo must be 1-50 chars: A-Z, 0-9, underscore, hyphen")
        return normalized

    @field_validator("floorNo")
    @classmethod
    def validate_floor_no(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("floorNo cannot be blank")
        return value

    @field_validator("intercom", "notes")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("flatType")
    @classmethod
    def validate_flat_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in FLAT_TYPE_VALUES:
                raise ValueError(f"flatType must be one of: {', '.join(FLAT_TYPE_VALUES)}")
        return value

    @field_validator("usageType")
    @classmethod
    def validate_usage_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in USAGE_TYPE_VALUES:
                raise ValueError(f"usageType must be one of: {', '.join(USAGE_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in FLAT_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(FLAT_STATUS_VALUES)}")
        return value

    @field_validator("ownershipType")
    @classmethod
    def validate_ownership(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in OWNERSHIP_TYPE_VALUES:
                raise ValueError(
                    f"ownershipType must be one of: {', '.join(OWNERSHIP_TYPE_VALUES)}"
                )
        return value

    @field_validator("areaType")
    @classmethod
    def validate_area_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in AREA_TYPE_VALUES:
                raise ValueError(f"areaType must be one of: {', '.join(AREA_TYPE_VALUES)}")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and not COLOR_REGEX.fullmatch(value):
            raise ValueError("color must be a hex value like #RGB or #RRGGBB")
        return value.upper() if value else value


class FlatUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    floorNo: Optional[str] = Field(None, min_length=1, max_length=20)
    flatType: Optional[str] = Field(None, max_length=50)
    usageType: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=32)
    ownershipType: Optional[str] = Field(None, max_length=32)
    areaSqft: Optional[float] = Field(None, ge=0, le=1_000_000)
    areaType: Optional[str] = Field(None, max_length=20)
    intercom: Optional[str] = Field(None, max_length=20)
    metadata: Optional[Dict[str, Any]] = None
    sequence: Optional[int] = Field(None, ge=0, le=9999)
    color: Optional[str] = Field(None, max_length=7)
    notes: Optional[str] = None

    @field_validator("floorNo")
    @classmethod
    def validate_floor_no(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value is not None and not value:
            raise ValueError("floorNo cannot be blank")
        return value

    @field_validator("intercom", "notes")
    @classmethod
    def strip_nullable_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("flatType")
    @classmethod
    def validate_flat_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in FLAT_TYPE_VALUES:
                raise ValueError(f"flatType must be one of: {', '.join(FLAT_TYPE_VALUES)}")
        return value

    @field_validator("usageType")
    @classmethod
    def validate_usage_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in USAGE_TYPE_VALUES:
                raise ValueError(f"usageType must be one of: {', '.join(USAGE_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in FLAT_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(FLAT_STATUS_VALUES)}")
        return value

    @field_validator("ownershipType")
    @classmethod
    def validate_ownership(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in OWNERSHIP_TYPE_VALUES:
                raise ValueError(
                    f"ownershipType must be one of: {', '.join(OWNERSHIP_TYPE_VALUES)}"
                )
        return value

    @field_validator("areaType")
    @classmethod
    def validate_area_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value:
            value = value.lower()
            if value not in AREA_TYPE_VALUES:
                raise ValueError(f"areaType must be one of: {', '.join(AREA_TYPE_VALUES)}")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if value and not COLOR_REGEX.fullmatch(value):
            raise ValueError("color must be a hex value like #RGB or #RRGGBB")
        return value.upper() if value else value


class FlatOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    wingId: UUID
    buildingName: Optional[str] = None
    buildingCode: Optional[str] = None
    wingName: Optional[str] = None
    wingCode: Optional[str] = None
    flatNo: str
    floorNo: str
    flatType: Optional[str] = None
    usageType: Optional[str] = None
    status: str
    ownershipType: Optional[str] = None
    areaSqft: Optional[float] = None
    areaType: Optional[str] = None
    intercom: Optional[str] = None
    metadata: Dict[str, Any]
    sequence: int
    color: Optional[str] = None
    notes: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_flat(
        cls,
        flat: Any,
        *,
        building_name: Optional[str] = None,
        building_code: Optional[str] = None,
        wing_name: Optional[str] = None,
        wing_code: Optional[str] = None,
    ) -> "FlatOut":
        return cls(
            id=flat.id,
            societyId=flat.society_id,
            buildingId=flat.building_id,
            wingId=flat.wing_id,
            buildingName=building_name,
            buildingCode=building_code,
            wingName=wing_name,
            wingCode=wing_code,
            flatNo=flat.flat_no,
            floorNo=flat.floor_no,
            flatType=flat.flat_type,
            usageType=flat.usage_type,
            status=flat.status,
            ownershipType=flat.ownership_type,
            areaSqft=flat.area_sqft,
            areaType=flat.area_type,
            intercom=flat.intercom,
            metadata=flat.metadata_json or {},
            sequence=flat.sequence,
            color=flat.color,
            notes=flat.notes,
            isActive=flat.is_active,
            version=flat.version,
            createdBy=flat.created_by,
            updatedBy=flat.updated_by,
            lastActivityAt=flat.last_activity_at,
            createdAt=flat.created_at,
            updatedAt=flat.updated_at,
        )
