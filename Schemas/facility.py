"""Pydantic schemas for Amenities Booking System (Phase 13)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Schemas.common import ListQueryParams
from Schemas.guard_facility_schema import GuardBookingListQueryParams
from Schemas.resident_facility_schema import ResidentBookingListQueryParams

AMENITY_CATEGORIES = (
    "clubhouse",
    "gym",
    "swimming_pool",
    "community_hall",
    "party_hall",
    "guest_room",
    "badminton_court",
    "tennis_court",
    "basketball_court",
    "cricket_ground",
    "children_play_area",
    "jogging_track",
    "conference_room",
    "bbq_area",
    "other",
)
AMENITY_STATUSES = ("active", "inactive", "maintenance", "retired")
BOOKING_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "confirmed",
    "checked_in",
    "checked_out",
    "cancelled",
    "completed",
    "expired",
)
PAYMENT_STATUSES = ("not_required", "pending", "paid", "refunded", "partially_refunded")

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _norm_enum(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validate_time(value: str, label: str) -> str:
    value = value.strip()
    if not TIME_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be in HH:MM 24-hour format")
    return value


def _validate_available_days(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-6]+", value):
        raise ValueError("availableDays must only contain digits 0-6 (0=Mon .. 6=Sun)")
    if len(set(value)) != len(value):
        raise ValueError("availableDays must not contain duplicate days")
    return value


# ---------------------------------------------------------------------------
# List query params
# ---------------------------------------------------------------------------


class FacilityListQueryParams(ListQueryParams):
    status: Optional[str] = None
    category: Optional[str] = None
    is_paid: Optional[bool] = Field(None, alias="isPaid")

    model_config = {"populate_by_name": True}


class BookingListQueryParams(ListQueryParams):
    status: Optional[str] = None
    amenity_id: Optional[UUID] = Field(None, alias="amenityId")
    from_date: Optional[date] = Field(None, alias="from")
    to_date: Optional[date] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Amenities
# ---------------------------------------------------------------------------


class FacilityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = Field(..., max_length=64)
    location: Optional[str] = Field(None, max_length=200)
    capacity: int = Field(default=1, ge=1)
    isPaid: bool = False
    pricePerSlot: int = Field(default=0, ge=0)
    securityDeposit: int = Field(default=0, ge=0)
    slotDurationMinutes: int = Field(default=60, ge=15, le=480)
    advanceBookingDays: int = Field(default=30, ge=1, le=365)
    cancellationHours: int = Field(default=24, ge=0, le=720)
    maxBookingsPerResident: Optional[int] = Field(default=2, ge=1, le=50)
    requiresApproval: bool = False
    operatingHoursStart: Optional[str] = None
    operatingHoursEnd: Optional[str] = None
    availableDays: str = Field(default="0123456", max_length=20)
    rulesText: Optional[str] = None
    imageUrl: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        value = _norm_enum(value)
        if value not in AMENITY_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(AMENITY_CATEGORIES)}")
        return value

    @field_validator("description", "location", "rulesText", "notes", "imageUrl")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("operatingHoursStart", "operatingHoursEnd")
    @classmethod
    def validate_operating_hours(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_time(value, "operatingHours")

    @field_validator("availableDays")
    @classmethod
    def validate_days(cls, value: str) -> str:
        result = _validate_available_days(value)
        return result or "0123456"

    @model_validator(mode="after")
    def validate_operating_window(self) -> "FacilityCreate":
        if self.operatingHoursStart and self.operatingHoursEnd:
            if self.operatingHoursEnd <= self.operatingHoursStart:
                raise ValueError("operatingHoursEnd must be after operatingHoursStart")
        if self.isPaid and self.pricePerSlot <= 0:
            raise ValueError("pricePerSlot must be greater than 0 for paid amenities")
        return self


class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=64)
    location: Optional[str] = Field(None, max_length=200)
    capacity: Optional[int] = Field(None, ge=1)
    isPaid: Optional[bool] = None
    pricePerSlot: Optional[int] = Field(None, ge=0)
    securityDeposit: Optional[int] = Field(None, ge=0)
    slotDurationMinutes: Optional[int] = Field(None, ge=15, le=480)
    advanceBookingDays: Optional[int] = Field(None, ge=1, le=365)
    cancellationHours: Optional[int] = Field(None, ge=0, le=720)
    maxBookingsPerResident: Optional[int] = Field(None, ge=1, le=50)
    requiresApproval: Optional[bool] = None
    operatingHoursStart: Optional[str] = None
    operatingHoursEnd: Optional[str] = None
    availableDays: Optional[str] = Field(None, max_length=20)
    rulesText: Optional[str] = None
    imageUrl: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in AMENITY_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(AMENITY_CATEGORIES)}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in AMENITY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(AMENITY_STATUSES)}")
        return value

    @field_validator("description", "location", "rulesText", "notes", "imageUrl")
    @classmethod
    def validate_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_optional_str(value)

    @field_validator("operatingHoursStart", "operatingHoursEnd")
    @classmethod
    def validate_operating_hours(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_time(value, "operatingHours")

    @field_validator("availableDays")
    @classmethod
    def validate_days(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_available_days(value)

    @model_validator(mode="after")
    def validate_operating_window(self) -> "FacilityUpdate":
        if self.operatingHoursStart and self.operatingHoursEnd:
            if self.operatingHoursEnd <= self.operatingHoursStart:
                raise ValueError("operatingHoursEnd must be after operatingHoursStart")
        return self


# ---------------------------------------------------------------------------
# Booking slots
# ---------------------------------------------------------------------------


class FacilityBookingSlotCreate(BaseModel):
    startDate: date
    endDate: date

    @model_validator(mode="after")
    def validate_range(self) -> "FacilityBookingSlotCreate":
        if self.endDate < self.startDate:
            raise ValueError("endDate cannot be before startDate")
        if (self.endDate - self.startDate).days > 90:
            raise ValueError("Slot generation range cannot exceed 90 days")
        return self


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


class FacilityBookingCreate(BaseModel):
    amenityId: UUID
    bookingDate: date
    startTime: str
    endTime: str
    guestCount: int = Field(default=0, ge=0, le=500)
    purpose: Optional[str] = Field(None, max_length=300)

    @field_validator("startTime", "endTime")
    @classmethod
    def validate_times(cls, value: str) -> str:
        return _validate_time(value, "time")

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("bookingDate")
    @classmethod
    def validate_booking_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("bookingDate cannot be in the past")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "FacilityBookingCreate":
        if self.endTime <= self.startTime:
            raise ValueError("endTime must be after startTime")
        return self


class BookingApproveRequest(BaseModel):
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BookingRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason cannot be blank")
        return value


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BookingCheckinRequest(BaseModel):
    bookingCode: Optional[str] = Field(None, min_length=4, max_length=20)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("bookingCode")
    @classmethod
    def validate_booking_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        return value or None

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BookingCheckoutRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


class BookingAdminUpdate(BaseModel):
    guestCount: Optional[int] = Field(None, ge=0, le=500)
    purpose: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = Field(None, max_length=2000)
    paymentStatus: Optional[str] = None

    @field_validator("purpose", "notes")
    @classmethod
    def validate_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)

    @field_validator("paymentStatus")
    @classmethod
    def validate_payment_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = _norm_enum(value)
        if value not in PAYMENT_STATUSES:
            raise ValueError(f"paymentStatus must be one of: {', '.join(PAYMENT_STATUSES)}")
        return value


class RefundRequest(BaseModel):
    bookingId: UUID
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_str(value)


# ---------------------------------------------------------------------------
# Maintenance blocks
# ---------------------------------------------------------------------------


class MaintenanceBlockCreate(BaseModel):
    amenityId: UUID
    startDate: date
    endDate: date
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "MaintenanceBlockCreate":
        if self.endDate < self.startDate:
            raise ValueError("endDate cannot be before startDate")
        return self
