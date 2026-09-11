"""Pydantic schemas for Parking Management System (Phase 14)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Schemas.common import ListQueryParams

ZONE_TYPES = ("basement", "open", "covered", "podium", "visitor", "ev", "other")
SLOT_CATEGORIES = ("standard", "reserved", "visitor", "ev", "disabled", "commercial")
SLOT_STATUSES = (
    "available",
    "allocated",
    "reserved",
    "occupied",
    "visitor",
    "maintenance",
    "blocked",
    "inactive",
)
VEHICLE_TYPES = ("car", "bike", "scooter", "ev", "commercial", "bicycle", "other")
VEHICLE_STATUSES = ("active", "inactive", "blocked")
ALLOCATION_TYPES = ("permanent", "temporary", "reserved")
ALLOCATION_STATUSES = ("active", "transferred", "revoked", "expired")
VISITOR_PARKING_STATUSES = ("requested", "active", "exited", "cancelled", "expired")
PAYMENT_STATUSES = ("not_required", "pending", "paid", "refunded")

VEHICLE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9\-\s]{4,32}$")


def _norm_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_vehicle_number(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip().upper())
    if not VEHICLE_NUMBER_PATTERN.fullmatch(value.replace(" ", "")):
        # Allow spaces in display but validate alphanumeric core
        core = value.replace(" ", "").replace("-", "")
        if len(core) < 4 or not re.fullmatch(r"[A-Z0-9]+", core):
            raise ValueError("vehicleNumber must be 4–32 alphanumeric characters")
    return value


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


class ParkingZoneListQueryParams(ListQueryParams):
    zone_type: Optional[str] = Field(None, alias="zoneType")
    building_id: Optional[UUID] = Field(None, alias="buildingId")

    model_config = {"populate_by_name": True}


class ParkingSlotListQueryParams(ListQueryParams):
    zone_id: Optional[UUID] = Field(None, alias="zoneId")
    status: Optional[str] = None
    slot_category: Optional[str] = Field(None, alias="slotCategory")

    model_config = {"populate_by_name": True}


class VehicleListQueryParams(ListQueryParams):
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    vehicle_type: Optional[str] = Field(None, alias="vehicleType")
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


class AllocationListQueryParams(ListQueryParams):
    status: Optional[str] = None
    resident_id: Optional[UUID] = Field(None, alias="residentId")
    slot_id: Optional[UUID] = Field(None, alias="slotId")
    vehicle_id: Optional[UUID] = Field(None, alias="vehicleId")

    model_config = {"populate_by_name": True}


class VisitorParkingListQueryParams(ListQueryParams):
    status: Optional[str] = None
    slot_id: Optional[UUID] = Field(None, alias="slotId")
    from_date: Optional[date] = Field(None, alias="from")
    to_date: Optional[date] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


class ParkingZoneCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    zoneType: str = Field(default="basement", max_length=32)
    floorLabel: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    isVisitorAllowed: bool = True
    monthlyFeeMinor: int = Field(default=0, ge=0)
    visitorFeeMinor: int = Field(default=0, ge=0)
    additionalVehicleFeeMinor: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

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

    @field_validator("zoneType")
    @classmethod
    def validate_zone_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in ZONE_TYPES:
            raise ValueError(f"zoneType must be one of: {', '.join(ZONE_TYPES)}")
        return value

    @field_validator("description", "floorLabel", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ParkingZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    zoneType: Optional[str] = Field(None, max_length=32)
    floorLabel: Optional[str] = Field(None, max_length=32)
    buildingId: Optional[UUID] = None
    isVisitorAllowed: Optional[bool] = None
    monthlyFeeMinor: Optional[int] = Field(None, ge=0)
    visitorFeeMinor: Optional[int] = Field(None, ge=0)
    additionalVehicleFeeMinor: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    isActive: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("zoneType")
    @classmethod
    def validate_zone_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in ZONE_TYPES:
            raise ValueError(f"zoneType must be one of: {', '.join(ZONE_TYPES)}")
        return value

    @field_validator("description", "floorLabel", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


class ParkingSlotCreate(BaseModel):
    zoneId: UUID
    slotCode: str = Field(..., min_length=1, max_length=32)
    label: Optional[str] = Field(None, max_length=64)
    slotCategory: str = Field(default="standard", max_length=32)
    vehicleTypesAllowed: str = Field(default="car,bike,scooter,ev", max_length=120)
    floorNo: Optional[int] = None
    isCovered: bool = False
    isEvCharging: bool = False
    monthlyFeeMinor: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("slotCode")
    @classmethod
    def validate_slot_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("slotCode cannot be blank")
        return value

    @field_validator("slotCategory")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in SLOT_CATEGORIES:
            raise ValueError(f"slotCategory must be one of: {', '.join(SLOT_CATEGORIES)}")
        return value

    @field_validator("vehicleTypesAllowed")
    @classmethod
    def validate_vehicle_types(cls, value: str) -> str:
        parts = [_norm_enum(p) for p in value.split(",") if p.strip()]
        if not parts:
            raise ValueError("vehicleTypesAllowed cannot be empty")
        for part in parts:
            if part not in VEHICLE_TYPES:
                raise ValueError(f"Invalid vehicle type: {part}")
        return ",".join(parts)

    @field_validator("label", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ParkingSlotUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=64)
    slotCategory: Optional[str] = Field(None, max_length=32)
    vehicleTypesAllowed: Optional[str] = Field(None, max_length=120)
    status: Optional[str] = None
    floorNo: Optional[int] = None
    isCovered: Optional[bool] = None
    isEvCharging: Optional[bool] = None
    monthlyFeeMinor: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    isActive: Optional[bool] = None

    @field_validator("slotCategory")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in SLOT_CATEGORIES:
            raise ValueError(f"slotCategory must be one of: {', '.join(SLOT_CATEGORIES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in SLOT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(SLOT_STATUSES)}")
        return value

    @field_validator("vehicleTypesAllowed")
    @classmethod
    def validate_vehicle_types(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        parts = [_norm_enum(p) for p in value.split(",") if p.strip()]
        if not parts:
            raise ValueError("vehicleTypesAllowed cannot be empty")
        for part in parts:
            if part not in VEHICLE_TYPES:
                raise ValueError(f"Invalid vehicle type: {part}")
        return ",".join(parts)

    @field_validator("label", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


class VehicleCreate(BaseModel):
    residentId: Optional[UUID] = None
    vehicleNumber: str = Field(..., min_length=4, max_length=32)
    vehicleType: str = Field(..., max_length=32)
    make: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=64)
    color: Optional[str] = Field(None, max_length=32)
    isPrimary: bool = False
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("vehicleNumber")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        return _normalize_vehicle_number(value)

    @field_validator("vehicleType")
    @classmethod
    def validate_vehicle_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in VEHICLE_TYPES:
            raise ValueError(f"vehicleType must be one of: {', '.join(VEHICLE_TYPES)}")
        return value

    @field_validator("make", "model", "color", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class VehicleUpdate(BaseModel):
    make: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=64)
    color: Optional[str] = Field(None, max_length=32)
    isPrimary: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in VEHICLE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VEHICLE_STATUSES)}")
        return value

    @field_validator("make", "model", "color", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------


class ParkingAllocateRequest(BaseModel):
    slotId: UUID
    residentId: UUID
    vehicleId: Optional[UUID] = None
    allocationType: str = Field(default="permanent", max_length=32)
    startDate: date
    endDate: Optional[date] = None
    monthlyFeeMinor: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None

    @field_validator("allocationType")
    @classmethod
    def validate_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in ALLOCATION_TYPES:
            raise ValueError(f"allocationType must be one of: {', '.join(ALLOCATION_TYPES)}")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "ParkingAllocateRequest":
        if self.endDate and self.endDate < self.startDate:
            raise ValueError("endDate cannot be before startDate")
        if self.allocationType == "temporary" and not self.endDate:
            raise ValueError("endDate is required for temporary allocations")
        return self


class ParkingTransferRequest(BaseModel):
    allocationId: UUID
    newSlotId: UUID
    vehicleId: Optional[UUID] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "ParkingTransferRequest":
        if self.startDate and self.endDate and self.endDate < self.startDate:
            raise ValueError("endDate cannot be before startDate")
        return self


class ParkingRevokeRequest(BaseModel):
    allocationId: UUID
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason cannot be blank")
        return value


# ---------------------------------------------------------------------------
# Entry / Exit / Visitor parking
# ---------------------------------------------------------------------------


class ParkingEntryRequest(BaseModel):
    parkingCode: Optional[str] = Field(None, min_length=4, max_length=20)
    vehicleNumber: Optional[str] = Field(None, min_length=4, max_length=32)
    slotId: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("parkingCode")
    @classmethod
    def validate_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        return value or None

    @field_validator("vehicleNumber")
    @classmethod
    def validate_vehicle_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_vehicle_number(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def require_identifier(self) -> "ParkingEntryRequest":
        if not self.parkingCode and not self.vehicleNumber and not self.slotId:
            raise ValueError("parkingCode, vehicleNumber, or slotId is required")
        return self


class ParkingExitRequest(BaseModel):
    parkingCode: Optional[str] = Field(None, min_length=4, max_length=20)
    vehicleNumber: Optional[str] = Field(None, min_length=4, max_length=32)
    slotId: Optional[UUID] = None
    visitorLogId: Optional[UUID] = None
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("parkingCode")
    @classmethod
    def validate_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        return value or None

    @field_validator("vehicleNumber")
    @classmethod
    def validate_vehicle_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_vehicle_number(value)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def require_identifier(self) -> "ParkingExitRequest":
        if (
            not self.parkingCode
            and not self.vehicleNumber
            and not self.slotId
            and not self.visitorLogId
        ):
            raise ValueError("parkingCode, vehicleNumber, slotId, or visitorLogId is required")
        return self


class VisitorParkingCreate(BaseModel):
    vehicleNumber: str = Field(..., min_length=4, max_length=32)
    vehicleType: str = Field(default="car", max_length=32)
    slotId: Optional[UUID] = None
    visitId: Optional[UUID] = None
    visitorId: Optional[UUID] = None
    residentId: Optional[UUID] = None
    purpose: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("vehicleNumber")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        return _normalize_vehicle_number(value)

    @field_validator("vehicleType")
    @classmethod
    def validate_vehicle_type(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in VEHICLE_TYPES:
            raise ValueError(f"vehicleType must be one of: {', '.join(VEHICLE_TYPES)}")
        return value

    @field_validator("purpose", "notes")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class ParkingRefundRequest(BaseModel):
    allocationId: Optional[UUID] = None
    visitorLogId: Optional[UUID] = None
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @model_validator(mode="after")
    def require_target(self) -> "ParkingRefundRequest":
        if not self.allocationId and not self.visitorLogId:
            raise ValueError("allocationId or visitorLogId is required")
        return self
