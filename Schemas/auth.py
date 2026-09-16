"""Pydantic schemas — replaces server/validators/auth.validator.js + request bodies."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from Constants.constants import (
    BLOOD_GROUP_VALUES,
    GENDER_VALUES,
    PASSWORD_REGEX,
    PHONE_REGEX,
    SOCIETY_ROLES,
    UserRole,
)


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(PASSWORD_REGEX, value):
        raise ValueError(
            "Password must contain uppercase, lowercase, a number, and a special character"
        )
    return value


def _validate_phone(value: str) -> str:
    if not re.fullmatch(PHONE_REGEX, value):
        raise ValueError("Valid 10-digit Indian phone number required")
    return value


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str
    password: str
    role: UserRole
    flatId: Optional[UUID] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        return _validate_phone(v.strip())

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("role")
    @classmethod
    def society_role_only(cls, v: UserRole) -> UserRole:
        if v.value not in SOCIETY_ROLES:
            raise ValueError("Platform roles cannot be self-registered")
        return v


class RegisterPublicRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str
    password: str
    role: UserRole

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        return _validate_phone(v.strip())

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("role")
    @classmethod
    def society_role_only(cls, v: UserRole) -> UserRole:
        if v.value not in SOCIETY_ROLES:
            raise ValueError("Platform roles cannot be self-registered")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    password: str

    @field_validator("otp")
    @classmethod
    def otp_ok(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("OTP must be a 6-digit number")
        return v

    @field_validator("password")
    @classmethod
    def password_ok(cls, v: str) -> str:
        return _validate_password(v)


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

    @field_validator("newPassword")
    @classmethod
    def new_password_len(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dob: Optional[datetime] = None
    gender: Optional[str] = None
    bloodGroup: Optional[str] = None
    flatNo: Optional[str] = None
    wing: Optional[str] = None
    building: Optional[str] = None
    designation: Optional[str] = None
    officeContact: Optional[str] = None
    officeAddress: Optional[str] = None
    address: Optional[str] = None
    emergencyName: Optional[str] = None
    emergencyPhone: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def gender_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in GENDER_VALUES:
            raise ValueError(f"gender must be one of: {', '.join(GENDER_VALUES)}")
        return v

    @field_validator("bloodGroup")
    @classmethod
    def blood_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if v not in BLOOD_GROUP_VALUES:
            raise ValueError(f"bloodGroup must be one of: {', '.join(BLOOD_GROUP_VALUES)}")
        return v

    def to_orm_updates(self) -> Dict[str, Any]:
        """Map camelCase API fields to snake_case ORM columns; '' → None."""
        mapping = {
            "dob": "dob",
            "gender": "gender",
            "bloodGroup": "blood_group",
            "flatNo": "flat_no",
            "wing": "wing",
            "building": "building",
            "designation": "designation",
            "officeContact": "office_contact",
            "officeAddress": "office_address",
            "address": "address",
            "emergencyName": "emergency_name",
            "emergencyPhone": "emergency_phone",
        }
        raw = self.model_dump(exclude_unset=True)
        updates: Dict[str, Any] = {}
        for api_key, orm_key in mapping.items():
            if api_key not in raw:
                continue
            value = raw[api_key]
            updates[orm_key] = None if value == "" else value
        return updates


class AuthUserPayload(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    phone: str
    role: str
    flat: Optional[UUID] = None
    societyId: Optional[UUID] = None
    isVerified: bool
    isActive: bool
    createdAt: datetime


class UserProfileOut(BaseModel):
    """Full profile for GET/PATCH profile — camelCase to match Node/Mongoose docs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    phone: str
    role: str
    flat: Optional[UUID] = None
    dob: Optional[datetime] = None
    gender: Optional[str] = None
    bloodGroup: Optional[str] = None
    flatNo: Optional[str] = None
    wing: Optional[str] = None
    building: Optional[str] = None
    designation: Optional[str] = None
    officeContact: Optional[str] = None
    officeAddress: Optional[str] = None
    address: Optional[str] = None
    emergencyName: Optional[str] = None
    emergencyPhone: Optional[str] = None
    isActive: bool
    isVerified: bool
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_user(cls, user: Any) -> "UserProfileOut":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            role=user.role,
            flat=user.flat_id,
            dob=user.dob,
            gender=user.gender,
            bloodGroup=user.blood_group,
            flatNo=user.flat_no,
            wing=user.wing,
            building=user.building,
            designation=user.designation,
            officeContact=user.office_contact,
            officeAddress=user.office_address,
            address=user.address,
            emergencyName=user.emergency_name,
            emergencyPhone=user.emergency_phone,
            isActive=user.is_active,
            isVerified=user.is_verified,
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )
