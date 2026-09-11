"""Schemas for resident portal endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from Schemas.visit import PASS_TYPE_VALUES, VISITOR_TYPE_VALUES
from Schemas.visitor import VisitorCreate


class ResidentVisitorInvitationCreate(BaseModel):
    visitorId: Optional[UUID] = None
    visitor: Optional[VisitorCreate] = None
    occupancyId: Optional[UUID] = None
    purpose: str = Field(..., min_length=1, max_length=200)
    visitorType: str = Field(..., max_length=32)
    passType: Optional[str] = Field(None, max_length=32)
    expectedAt: Optional[datetime] = None
    scheduledAt: Optional[datetime] = None
    vehicleNumber: Optional[str] = Field(None, max_length=30)
    numberOfPeople: int = Field(default=1, ge=1, le=50)
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
        normalized = value.strip().lower()
        if normalized not in VISITOR_TYPE_VALUES:
            raise ValueError(f"visitorType must be one of: {', '.join(VISITOR_TYPE_VALUES)}")
        return normalized

    @field_validator("passType")
    @classmethod
    def validate_pass_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in PASS_TYPE_VALUES:
            raise ValueError(f"passType must be one of: {', '.join(PASS_TYPE_VALUES)}")
        return normalized

    @field_validator("notes", "vehicleNumber")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ResidentVisitorApprovalRequest(BaseModel):
    visitId: UUID
    action: Literal["approve", "reject", "cancel"]
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
