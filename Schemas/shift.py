"""Pydantic schemas for Shift and Staff Attendance."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from Schemas.common import ListQueryParams

SHIFT_TYPE_VALUES = ("morning", "evening", "night", "custom")

SHIFT_STATUS_VALUES = ("scheduled", "active", "completed", "cancelled", "no_show")

ATTENDANCE_STATUS_VALUES = ("checked_in", "checked_out", "voided")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ShiftListQueryParams(ListQueryParams):
    staff_id: Optional[UUID] = Field(None, alias="staffId")
    gate_id: Optional[UUID] = Field(None, alias="gateId")
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    status: Optional[str] = None
    shift_type: Optional[str] = Field(None, alias="shiftType")
    shift_date: Optional[date] = Field(None, alias="shiftDate")
    from_date: Optional[date] = Field(None, alias="fromDate")
    to_date: Optional[date] = Field(None, alias="toDate")

    model_config = {"populate_by_name": True}


class ShiftCreate(BaseModel):
    staffId: UUID
    gateId: Optional[UUID] = None
    shiftDate: date
    shiftType: str = Field(default="custom", max_length=32)
    scheduledStart: datetime
    scheduledEnd: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("shiftType")
    @classmethod
    def validate_shift_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in SHIFT_TYPE_VALUES:
            raise ValueError(f"shiftType must be one of: {', '.join(SHIFT_TYPE_VALUES)}")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ShiftUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gateId: Optional[UUID] = None
    shiftType: Optional[str] = Field(None, max_length=32)
    scheduledStart: Optional[datetime] = None
    scheduledEnd: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("shiftType")
    @classmethod
    def validate_shift_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in SHIFT_TYPE_VALUES:
            raise ValueError(f"shiftType must be one of: {', '.join(SHIFT_TYPE_VALUES)}")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ShiftNotes(BaseModel):
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ShiftOut(BaseModel):
    id: UUID
    societyId: UUID
    staffId: UUID
    staffName: Optional[str] = None
    staffCode: Optional[str] = None
    gateId: Optional[UUID] = None
    gateName: Optional[str] = None
    buildingId: Optional[UUID] = None
    shiftDate: date
    shiftType: str
    scheduledStart: datetime
    scheduledEnd: datetime
    actualStart: Optional[datetime] = None
    actualEnd: Optional[datetime] = None
    status: str
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
    def from_orm_shift(
        cls,
        shift: Any,
        *,
        staff_name: Optional[str] = None,
        staff_code: Optional[str] = None,
        gate_name: Optional[str] = None,
    ) -> "ShiftOut":
        return cls(
            id=shift.id,
            societyId=shift.society_id,
            staffId=shift.staff_id,
            staffName=staff_name,
            staffCode=staff_code,
            gateId=shift.gate_id,
            gateName=gate_name,
            buildingId=shift.building_id,
            shiftDate=shift.shift_date,
            shiftType=shift.shift_type,
            scheduledStart=shift.scheduled_start,
            scheduledEnd=shift.scheduled_end,
            actualStart=shift.actual_start,
            actualEnd=shift.actual_end,
            status=shift.status,
            metadata=shift.metadata_json or {},
            notes=shift.notes,
            isActive=shift.is_active,
            version=shift.version,
            createdBy=shift.created_by,
            updatedBy=shift.updated_by,
            lastActivityAt=shift.last_activity_at,
            createdAt=shift.created_at,
            updatedAt=shift.updated_at,
        )


class AttendanceListQueryParams(ListQueryParams):
    staff_id: Optional[UUID] = Field(None, alias="staffId")
    gate_id: Optional[UUID] = Field(None, alias="gateId")
    shift_id: Optional[UUID] = Field(None, alias="shiftId")
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


class AttendanceCheckIn(BaseModel):
    staffId: UUID
    shiftId: Optional[UUID] = None
    gateId: Optional[UUID] = None
    checkInTime: Optional[datetime] = None
    notes: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    accuracyMeters: Optional[float] = Field(None, ge=0, le=10000)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_coordinates_pair(self) -> "AttendanceCheckIn":
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class AttendanceCheckOut(BaseModel):
    checkOutTime: Optional[datetime] = None
    notes: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    accuracyMeters: Optional[float] = Field(None, ge=0, le=10000)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_coordinates_pair(self) -> "AttendanceCheckOut":
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class AttendanceOut(BaseModel):
    id: UUID
    societyId: UUID
    staffId: UUID
    staffName: Optional[str] = None
    shiftId: Optional[UUID] = None
    gateId: Optional[UUID] = None
    gateName: Optional[str] = None
    status: str
    checkInTime: datetime
    checkOutTime: Optional[datetime] = None
    recordedBy: Optional[UUID] = None
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
    def from_orm_attendance(
        cls,
        row: Any,
        *,
        staff_name: Optional[str] = None,
        gate_name: Optional[str] = None,
    ) -> "AttendanceOut":
        return cls(
            id=row.id,
            societyId=row.society_id,
            staffId=row.staff_id,
            staffName=staff_name,
            shiftId=row.shift_id,
            gateId=row.gate_id,
            gateName=gate_name,
            status=row.status,
            checkInTime=row.check_in_time,
            checkOutTime=row.check_out_time,
            recordedBy=row.recorded_by,
            metadata=row.metadata_json or {},
            notes=row.notes,
            isActive=row.is_active,
            version=row.version,
            createdBy=row.created_by,
            updatedBy=row.updated_by,
            lastActivityAt=row.last_activity_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )
