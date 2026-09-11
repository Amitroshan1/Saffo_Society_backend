"""Pydantic schemas for Occupancy module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

OCCUPANCY_ROLE_VALUES = ("owner", "tenant", "family_member", "domestic_help")
OCCUPANCY_STATUS_VALUES = ("active", "ended", "cancelled")
ENDED_REASON_VALUES = ("moved_out", "lease_ended", "transfer", "deceased", "other")


class OccupancyListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    wing_id: Optional[UUID] = Field(None, alias="wingId")
    flat_id: Optional[UUID] = Field(None, alias="flatId")
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    role: Optional[str] = None
    status: Optional[str] = None
    is_primary: Optional[bool] = Field(None, alias="isPrimary")
    current_only: Optional[bool] = Field(None, alias="currentOnly")

    model_config = {"populate_by_name": True}


class OccupancyCreate(BaseModel):
    flatId: UUID
    residentId: UUID
    role: str = Field(..., max_length=32)
    moveInDate: date
    isPrimary: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in OCCUPANCY_ROLE_VALUES:
            raise ValueError(f"role must be one of: {', '.join(OCCUPANCY_ROLE_VALUES)}")
        return value

    @field_validator("isPrimary")
    @classmethod
    def validate_primary(cls, value: bool, info) -> bool:
        role = info.data.get("role")
        if value and role == "domestic_help":
            raise ValueError("domestic_help cannot be primary")
        return value


class OccupancyUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Optional[str] = Field(None, max_length=32)
    isPrimary: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in OCCUPANCY_ROLE_VALUES:
            raise ValueError(f"role must be one of: {', '.join(OCCUPANCY_ROLE_VALUES)}")
        return value


class OccupancyMoveOut(BaseModel):
    moveOutDate: Optional[date] = None
    endedReason: str = Field(default="moved_out", max_length=64)
    notes: Optional[str] = None

    @field_validator("endedReason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ENDED_REASON_VALUES:
            raise ValueError(f"endedReason must be one of: {', '.join(ENDED_REASON_VALUES)}")
        return value


class OccupancyOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    wingId: UUID
    flatId: UUID
    residentId: UUID
    role: str
    isPrimary: bool
    status: str
    moveInDate: date
    moveOutDate: Optional[date] = None
    endedReason: Optional[str] = None
    flatNo: Optional[str] = None
    floorNo: Optional[str] = None
    wingCode: Optional[str] = None
    wingName: Optional[str] = None
    buildingName: Optional[str] = None
    buildingCode: Optional[str] = None
    residentName: Optional[str] = None
    residentCode: Optional[str] = None
    residentPhone: Optional[str] = None
    userId: Optional[UUID] = None
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
    def from_orm_occupancy(
        cls,
        occ: Any,
        *,
        flat_no: Optional[str] = None,
        floor_no: Optional[str] = None,
        wing_code: Optional[str] = None,
        wing_name: Optional[str] = None,
        building_name: Optional[str] = None,
        building_code: Optional[str] = None,
        resident_name: Optional[str] = None,
        resident_code: Optional[str] = None,
        resident_phone: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> "OccupancyOut":
        return cls(
            id=occ.id,
            societyId=occ.society_id,
            buildingId=occ.building_id,
            wingId=occ.wing_id,
            flatId=occ.flat_id,
            residentId=occ.resident_id,
            role=occ.role,
            isPrimary=occ.is_primary,
            status=occ.status,
            moveInDate=occ.move_in_date,
            moveOutDate=occ.move_out_date,
            endedReason=occ.ended_reason,
            flatNo=flat_no,
            floorNo=floor_no,
            wingCode=wing_code,
            wingName=wing_name,
            buildingName=building_name,
            buildingCode=building_code,
            residentName=resident_name,
            residentCode=resident_code,
            residentPhone=resident_phone,
            userId=user_id,
            metadata=occ.metadata_json or {},
            notes=occ.notes,
            isActive=occ.is_active,
            version=occ.version,
            createdBy=occ.created_by,
            updatedBy=occ.updated_by,
            lastActivityAt=occ.last_activity_at,
            createdAt=occ.created_at,
            updatedAt=occ.updated_at,
        )
