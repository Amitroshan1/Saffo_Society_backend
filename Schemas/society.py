"""Pydantic schemas for Society module."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

GSTIN_REGEX = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
CODE_REGEX = re.compile(r"^[A-Z0-9-]{3,32}$")
PINCODE_IN_REGEX = re.compile(r"^\d{6}$")

VISITOR_APPROVAL_VALUES = ("resident", "guard", "admin")
THEME_VALUES = ("system", "light", "dark")


class SocietySettings(BaseModel):
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    language: str = "en"
    date_format: str = "DD/MM/YYYY"
    theme: str = "system"
    visitorApproval: str = "resident"
    financialYearStart: int = 4

    @field_validator("currency")
    @classmethod
    def currency_ok(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 3:
            raise ValueError("currency must be a 3-letter ISO code")
        return v

    @field_validator("theme")
    @classmethod
    def theme_ok(cls, v: str) -> str:
        if v not in THEME_VALUES:
            raise ValueError(f"theme must be one of: {', '.join(THEME_VALUES)}")
        return v

    @field_validator("visitorApproval")
    @classmethod
    def visitor_ok(cls, v: str) -> str:
        if v not in VISITOR_APPROVAL_VALUES:
            raise ValueError(
                f"visitorApproval must be one of: {', '.join(VISITOR_APPROVAL_VALUES)}"
            )
        return v

    @field_validator("financialYearStart")
    @classmethod
    def fy_ok(cls, v: int) -> int:
        if v < 1 or v > 12:
            raise ValueError("financialYearStart must be 1-12")
        return v


def _validate_in_tax_ids(country: str, gstin: Optional[str], pan: Optional[str]) -> None:
    if (country or "IN").upper() != "IN":
        return
    if gstin and not GSTIN_REGEX.fullmatch(gstin.upper()):
        raise ValueError("Invalid GSTIN format")
    if pan and not PAN_REGEX.fullmatch(pan.upper()):
        raise ValueError("Invalid PAN format")


class SocietyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    shortName: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    code: str = Field(..., min_length=3, max_length=32)
    registrationNo: Optional[str] = Field(None, max_length=64)
    registrationDate: Optional[date] = None
    gstin: Optional[str] = Field(None, max_length=15)
    pan: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    contactPerson: Optional[str] = Field(None, max_length=120)
    contactDesignation: Optional[str] = Field(None, max_length=100)
    contactEmail: Optional[EmailStr] = None
    contactPhone: Optional[str] = Field(None, max_length=20)
    addressLine1: str = Field(..., min_length=1, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    pincode: str = Field(..., min_length=1, max_length=10)
    country: str = Field(default="IN", min_length=2, max_length=2)
    website: Optional[str] = Field(None, max_length=255)
    logoUrl: Optional[str] = Field(None, max_length=500)
    coverImage: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    establishedYear: Optional[int] = None
    settings: Optional[SocietySettings] = None

    @field_validator("name", "addressLine1", "city", "state", "pincode")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be blank")
        return v

    @field_validator("code")
    @classmethod
    def code_ok(cls, v: str) -> str:
        v = v.strip().upper()
        if not CODE_REGEX.fullmatch(v):
            raise ValueError("code must be 3-32 chars: A-Z, 0-9, hyphen")
        return v

    @field_validator("country")
    @classmethod
    def country_ok(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("gstin", "pan")
    @classmethod
    def upper_tax(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v

    @field_validator("establishedYear")
    @classmethod
    def year_ok(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        year = datetime.now().year
        if v < 1800 or v > year:
            raise ValueError(f"establishedYear must be between 1800 and {year}")
        return v

    @model_validator(mode="after")
    def validate_country_rules(self) -> "SocietyCreate":
        if self.country == "IN" and not PINCODE_IN_REGEX.fullmatch(self.pincode):
            raise ValueError("pincode must be 6 digits for India")
        _validate_in_tax_ids(self.country, self.gstin, self.pan)
        return self


class SocietyUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(None, min_length=2, max_length=200)
    displayName: Optional[str] = Field(None, max_length=200)
    shortName: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    registrationNo: Optional[str] = Field(None, max_length=64)
    registrationDate: Optional[date] = None
    gstin: Optional[str] = Field(None, max_length=15)
    pan: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    contactPerson: Optional[str] = Field(None, max_length=120)
    contactDesignation: Optional[str] = Field(None, max_length=100)
    contactEmail: Optional[EmailStr] = None
    contactPhone: Optional[str] = Field(None, max_length=20)
    addressLine1: Optional[str] = Field(None, min_length=1, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    pincode: Optional[str] = Field(None, min_length=1, max_length=10)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    website: Optional[str] = Field(None, max_length=255)
    logoUrl: Optional[str] = Field(None, max_length=500)
    coverImage: Optional[str] = Field(None, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    establishedYear: Optional[int] = None
    settings: Optional[SocietySettings] = None

    @field_validator("country")
    @classmethod
    def country_ok(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v

    @field_validator("gstin", "pan")
    @classmethod
    def upper_tax(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class SocietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    displayName: Optional[str] = None
    shortName: Optional[str] = None
    description: Optional[str] = None
    code: str
    registrationNo: Optional[str] = None
    registrationDate: Optional[date] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    contactDesignation: Optional[str] = None
    contactEmail: Optional[str] = None
    contactPhone: Optional[str] = None
    addressLine1: str
    addressLine2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str
    website: Optional[str] = None
    logoUrl: Optional[str] = None
    coverImage: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    establishedYear: Optional[int] = None
    settings: Dict[str, Any]
    isActive: bool
    version: int
    createdBy: Optional[UUID] = None
    updatedBy: Optional[UUID] = None
    lastActivityAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_society(cls, s: Any) -> "SocietyOut":
        return cls(
            id=s.id,
            name=s.name,
            displayName=s.display_name,
            shortName=s.short_name,
            description=s.description,
            code=s.code,
            registrationNo=s.registration_no,
            registrationDate=s.registration_date,
            gstin=s.gstin,
            pan=s.pan,
            email=s.email,
            phone=s.phone,
            contactPerson=s.contact_person,
            contactDesignation=s.contact_designation,
            contactEmail=s.contact_email,
            contactPhone=s.contact_phone,
            addressLine1=s.address_line1,
            addressLine2=s.address_line2,
            city=s.city,
            state=s.state,
            pincode=s.pincode,
            country=s.country,
            website=s.website,
            logoUrl=s.logo_url,
            coverImage=s.cover_image,
            latitude=s.latitude,
            longitude=s.longitude,
            establishedYear=s.established_year,
            settings=s.settings or {},
            isActive=s.is_active,
            version=s.version,
            createdBy=s.created_by,
            updatedBy=s.updated_by,
            lastActivityAt=s.last_activity_at,
            createdAt=s.created_at,
            updatedAt=s.updated_at,
        )
