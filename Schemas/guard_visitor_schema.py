"""Guard walk-in visitor request/query schemas."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from Schemas.common import ListQueryParams


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class GuardVisitorListQueryParams(ListQueryParams):
    status: Optional[str] = None
    purpose: Optional[str] = None

    model_config = {"populate_by_name": True}


class GuardVisitorCreate(BaseModel):
    """Walk-in payload. Accepts frontend aliases (flat/persons/vehicle/photo)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=20)
    purpose: str = Field(default="Guest", min_length=1, max_length=200)
    persons: int = Field(default=1, ge=1, le=50, alias="persons_count")
    vehicle: Optional[str] = Field(None, max_length=30, alias="vehicle_number")
    vehicleType: Optional[str] = Field(None, max_length=30, alias="vehicle_type")
    flat: Optional[str] = Field(None, max_length=80)
    flatId: Optional[UUID] = Field(None, alias="flat_id")
    occupancyId: Optional[UUID] = Field(None, alias="occupancy_id")
    remarks: Optional[str] = Field(None, max_length=1000)
    photoUrl: Optional[str] = Field(None, alias="photo_url")
    photo: Optional[str] = None
    notifyResident: bool = Field(default=True, alias="notify_resident")
    preApproved: bool = Field(default=False, alias="pre_approved")

    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        mapping = {
            "notify": "notifyResident",
            "notify_resident": "notifyResident",
            "preapprove": "preApproved",
            "pre_approved": "preApproved",
            "persons_count": "persons",
            "vehicle_number": "vehicle",
            "vehicle_type": "vehicleType",
            "photo_url": "photoUrl",
            "flat_id": "flatId",
            "occupancy_id": "occupancyId",
        }
        out = dict(data)
        for old, new in mapping.items():
            if old in out and new not in out:
                out[new] = out[old]
        return out

    @field_validator("name", "phone", "purpose")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("vehicle", "vehicleType", "flat", "remarks", "photoUrl", "photo")
    @classmethod
    def optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("notifyResident", "preApproved", mode="before")
    @classmethod
    def parse_bool(cls, value: Any) -> bool:
        return _as_bool(value)

    @field_validator("persons", mode="before")
    @classmethod
    def parse_persons(cls, value: Any) -> int:
        if value in (None, ""):
            return 1
        return int(value)


class GuardVisitorDecision(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    rejectedBy: Optional[str] = Field(default="Guard", alias="rejected_by")
    notes: Optional[str] = None


class GuardOtpVerify(BaseModel):
    otp: str = Field(..., min_length=4, max_length=20)

    @field_validator("otp")
    @classmethod
    def strip_otp(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("otp cannot be blank")
        return value


class GuardCallLogCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    visitorId: UUID = Field(..., alias="visitor_id")
    notes: Optional[str] = None
