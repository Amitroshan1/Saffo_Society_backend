"""Analytics Pydantic schemas (Phase 16)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyticsFilterParams(BaseModel):
    buildingId: Optional[str] = None
    wingId: Optional[str] = None
    flatId: Optional[str] = None
    fromDate: Optional[str] = Field(None, alias="from")
    toDate: Optional[str] = Field(None, alias="to")
    month: Optional[int] = None
    quarter: Optional[int] = None
    year: Optional[int] = None
    status: Optional[str] = None
    category: Optional[str] = None
    role: Optional[str] = None
    granularity: Optional[str] = None
    page: int = 1
    pageSize: int = 20
    search: Optional[str] = None

    class Config:
        populate_by_name = True


class ExportCreateRequest(BaseModel):
    reportKey: str
    format: str = "csv"
    filters: dict[str, Any] = Field(default_factory=dict)


class ScheduleCreateRequest(BaseModel):
    name: str
    reportKey: str
    format: str = "csv"
    frequency: str = "monthly"
    cronExpression: Optional[str] = None
    filters: dict[str, Any] = Field(default_factory=dict)
    recipientUserIds: list[str] = Field(default_factory=list)
    recipientRoles: list[str] = Field(default_factory=list)


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    reportKey: Optional[str] = None
    format: Optional[str] = None
    frequency: Optional[str] = None
    cronExpression: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    isActive: Optional[bool] = None


class PreferencesUpdateRequest(BaseModel):
    favoriteReportKeys: Optional[list[str]] = None
    defaultFilters: Optional[dict[str, Any]] = None
    savedFilters: Optional[list[dict[str, Any]]] = None


class RebuildRequest(BaseModel):
    fromDate: Optional[str] = None
    toDate: Optional[str] = None
