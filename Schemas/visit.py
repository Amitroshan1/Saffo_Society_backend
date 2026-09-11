"""Pydantic schemas for Visit lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from Schemas.common import ListQueryParams

VISITOR_TYPE_VALUES = (
    "guest",
    "delivery",
    "maid",
    "driver",
    "technician",
    "vendor",
    "courier",
    "other",
)

VISIT_STATUS_VALUES = (
    "scheduled",
    "waiting",
    "approved",
    "rejected",
    "checked_in",
    "checked_out",
    "cancelled",
    "expired",
)

PASS_TYPE_VALUES = ("one_time", "daily", "temporary", "service", "delivery")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class VisitListQueryParams(ListQueryParams):
    building_id: Optional[UUID] = Field(None, alias="buildingId")
    wing_id: Optional[UUID] = Field(None, alias="wingId")
    flat_id: Optional[UUID] = Field(None, alias="flatId")
    occupancy_id: Optional[UUID] = Field(None, alias="occupancyId")
    visitor_id: Optional[UUID] = Field(None, alias="visitorId")
    status: Optional[str] = None
    visitor_type: Optional[str] = Field(None, alias="visitorType")
    pass_type: Optional[str] = Field(None, alias="passType")
    is_preapproved: Optional[bool] = Field(None, alias="isPreapproved")
    from_date: Optional[datetime] = Field(None, alias="fromDate")
    to_date: Optional[datetime] = Field(None, alias="toDate")

    model_config = {"populate_by_name": True}


class VisitCreate(BaseModel):
    occupancyId: UUID
    visitorId: UUID
    purpose: str = Field(..., min_length=1, max_length=200)
    visitorType: str = Field(..., max_length=32)
    passType: Optional[str] = Field(None, max_length=32)
    status: str = Field(default="scheduled", max_length=32)
    scheduledAt: Optional[datetime] = None
    expectedAt: Optional[datetime] = None
    vehicleNumber: Optional[str] = Field(None, max_length=30)
    numberOfPeople: int = Field(default=1, ge=1, le=50)
    isPreapproved: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("purpose cannot be blank")
        return value

    @field_validator("visitorType")
    @classmethod
    def validate_visitor_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VISITOR_TYPE_VALUES:
            raise ValueError(f"visitorType must be one of: {', '.join(VISITOR_TYPE_VALUES)}")
        return value

    @field_validator("passType")
    @classmethod
    def validate_pass_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if not value:
            return None
        value = value.lower()
        if value not in PASS_TYPE_VALUES:
            raise ValueError(f"passType must be one of: {', '.join(PASS_TYPE_VALUES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VISIT_STATUS_VALUES:
            raise ValueError(f"status must be one of: {', '.join(VISIT_STATUS_VALUES)}")
        return value

    @field_validator("vehicleNumber", "notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitDecision(BaseModel):
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitCheckIn(BaseModel):
    checkInTime: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitCheckOut(BaseModel):
    checkOutTime: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VisitOut(BaseModel):
    id: UUID
    societyId: UUID
    buildingId: UUID
    wingId: UUID
    flatId: UUID
    occupancyId: UUID
    visitorId: UUID
    purpose: str
    visitorType: str
    passType: Optional[str] = None
    status: str
    scheduledAt: Optional[datetime] = None
    expectedAt: Optional[datetime] = None
    checkInTime: Optional[datetime] = None
    checkOutTime: Optional[datetime] = None
    approvedBy: Optional[UUID] = None
    gateInBy: Optional[UUID] = None
    gateOutBy: Optional[UUID] = None
    vehicleNumber: Optional[str] = None
    numberOfPeople: int
    qrCode: Optional[str] = None
    otp: Optional[str] = None
    isPreapproved: bool
    metadata: Dict[str, Any]
    notes: Optional[str] = None
    visitorName: Optional[str] = None
    visitorPhone: Optional[str] = None
    flatNo: Optional[str] = None
    wingCode: Optional[str] = None
    buildingCode: Optional[str] = None
    residentName: Optional[str] = None
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_visit(
        cls,
        visit: Any,
        *,
        visitor_name: Optional[str] = None,
        visitor_phone: Optional[str] = None,
        flat_no: Optional[str] = None,
        wing_code: Optional[str] = None,
        building_code: Optional[str] = None,
        resident_name: Optional[str] = None,
    ) -> "VisitOut":
        return cls(
            id=visit.id,
            societyId=visit.society_id,
            buildingId=visit.building_id,
            wingId=visit.wing_id,
            flatId=visit.flat_id,
            occupancyId=visit.occupancy_id,
            visitorId=visit.visitor_id,
            purpose=visit.purpose,
            visitorType=visit.visitor_type,
            passType=visit.pass_type,
            status=visit.status,
            scheduledAt=visit.scheduled_at,
            expectedAt=visit.expected_at,
            checkInTime=visit.check_in_time,
            checkOutTime=visit.check_out_time,
            approvedBy=visit.approved_by,
            gateInBy=visit.gate_in_by,
            gateOutBy=visit.gate_out_by,
            vehicleNumber=visit.vehicle_number,
            numberOfPeople=visit.number_of_people,
            qrCode=visit.qr_code,
            otp=visit.otp,
            isPreapproved=visit.is_preapproved,
            metadata=visit.metadata_json or {},
            notes=visit.notes,
            visitorName=visitor_name,
            visitorPhone=visitor_phone,
            flatNo=flat_no,
            wingCode=wing_code,
            buildingCode=building_code,
            residentName=resident_name,
            isActive=visit.is_active,
            version=visit.version,
            createdBy=visit.created_by,
            updatedBy=visit.updated_by,
            lastActivityAt=visit.last_activity_at,
            createdAt=visit.created_at,
            updatedAt=visit.updated_at,
        )


class VisitUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    purpose: Optional[str] = Field(None, min_length=1, max_length=200)
    passType: Optional[str] = Field(None, max_length=32)
    visitorType: Optional[str] = Field(None, max_length=32)
    expectedAt: Optional[datetime] = None
    vehicleNumber: Optional[str] = Field(None, max_length=30)
    numberOfPeople: Optional[int] = Field(None, ge=1, le=50)
    metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("purpose", "vehicleNumber", "notes")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("passType")
    @classmethod
    def validate_pass_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if not value:
            return None
        value = value.lower()
        if value not in PASS_TYPE_VALUES:
            raise ValueError(f"passType must be one of: {', '.join(PASS_TYPE_VALUES)}")
        return value

    @field_validator("visitorType")
    @classmethod
    def validate_visitor_type(cls, value: Optional[str]) -> Optional[str]:
        value = _normalize_optional_str(value)
        if not value:
            return None
        value = value.lower()
        if value not in VISITOR_TYPE_VALUES:
            raise ValueError(f"visitorType must be one of: {', '.join(VISITOR_TYPE_VALUES)}")
        return value
