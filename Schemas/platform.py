"""Pydantic schemas for Phase 17 platform APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TenantCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=64)
    displayName: Optional[str] = None
    adminEmail: EmailStr
    planCode: str = "trial"
    region: str = "IN"
    timezone: str = "Asia/Kolkata"
    isolationMode: str = "shared"
    notes: Optional[str] = None


class TenantUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    displayName: Optional[str] = None
    adminEmail: Optional[EmailStr] = None
    planCode: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None


class CloneDemoRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=200)
    adminEmail: EmailStr


class PlanUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: Optional[str] = None
    description: Optional[str] = None
    billingPeriod: Optional[str] = None
    priceMinor: Optional[int] = None
    currency: Optional[str] = None
    trialDays: Optional[int] = None
    limits: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None
    isPublic: Optional[bool] = None
    sortOrder: Optional[int] = None


class AssignPlanRequest(BaseModel):
    planCode: str


class LicenseIssueRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    validDays: int = 365
    limits: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, Any]] = None
    licenseKey: Optional[str] = None


class FeatureFlagUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    name: Optional[str] = None
    description: Optional[str] = None
    defaultEnabled: Optional[bool] = None
    rolloutPercent: Optional[int] = None
    tags: Optional[List[str]] = None


class TenantFlagOverride(BaseModel):
    key: str
    mode: str = "inherit"


class TenantFlagsRequest(BaseModel):
    overrides: List[TenantFlagOverride]


class SettingsPatch(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)
    secretRefs: Optional[Dict[str, str]] = None


class MaintenanceRequest(BaseModel):
    enabled: bool
    message: Optional[str] = None


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1)
    type: str = "broadcast"
    priority: str = "normal"
    scheduledAt: Optional[datetime] = None
    targetRoles: Optional[List[str]] = None


class ImpersonateRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class PlatformUserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    email: EmailStr
    phone: str
    role: str = "platform_support"
    password: Optional[str] = None
    designation: Optional[str] = None


class PlatformUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None
