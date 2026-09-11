"""Pydantic schemas for Gate module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

GATE_TYPE_VALUES = (
    "main",
    "service",
    "pedestrian",
    "vehicle",
    "basement",
    "emergency",
    "other",
)


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class GateListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    gate_type: Optional[str] = Field(None, alias="gateType")

    model_config = {"populate_by_name": True}


class GateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    gateType: str = Field(..., max_length=32)
    buildingId: Optional[UUID] = None
    locationDescription: Optional[str] = Field(None, max_length=500)
    sequence: int = Field(default=0, ge=0, le=9999)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip().upper()
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

    @field_validator("gateType")
    @classmethod
    def validate_gate_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in GATE_TYPE_VALUES:
            raise ValueError(f"gateType must be one of: {', '.join(GATE_TYPE_VALUES)}")
        return value

    @field_validator("locationDescription", "notes")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class GateUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    gateType: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    locationDescription: Optional[str] = Field(None, max_length=500)
    sequence: Optional[int] = Field(None, ge=0, le=9999)
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("name", "locationDescription", "notes")
    @classmethod
    def strip_nullable(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("gateType")
    @classmethod
    def validate_gate_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in GATE_TYPE_VALUES:
            raise ValueError(f"gateType must be one of: {', '.join(GATE_TYPE_VALUES)}")
        return value


class GateOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: Optional[UUID] = None
    buildingName: Optional[str] = None
    code: str
    name: str
    gateType: str
    locationDescription: Optional[str] = None
    sequence: int
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
    def from_orm_gate(cls, gate: Any, *, building_name: Optional[str] = None) -> "GateOut":
        return cls(
            id=gate.id,
            societyId=gate.society_id,
            buildingId=gate.building_id,
            buildingName=building_name,
            code=gate.code,
            name=gate.name,
            gateType=gate.gate_type,
            locationDescription=gate.location_description,
            sequence=gate.sequence,
            metadata=gate.metadata_json or {},
            notes=gate.notes,
            isActive=gate.is_active,
            version=gate.version,
            createdBy=gate.created_by,
            updatedBy=gate.updated_by,
            lastActivityAt=gate.last_activity_at,
            createdAt=gate.created_at,
            updatedAt=gate.updated_at,
        )
