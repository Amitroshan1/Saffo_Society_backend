"""Reports & Analytics SQLAlchemy models (Phase 16)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


def _audit_cols_mixin_end():
    """Marker — audit columns defined inline on each model for clarity."""


class AnalyticsReportDefinition(Base):
    __tablename__ = "analytics_report_definitions"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "report_key", name="uq_analytics_report_defs_society_key"
        ),
        Index("ix_analytics_report_defs_society_id", "society_id"),
        Index("ix_analytics_report_defs_category", "category"),
        Index("ix_analytics_report_defs_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="fact_query")
    roles_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    columns_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    default_filters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    chart_types_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsKpiDefinition(Base):
    __tablename__ = "analytics_kpi_definitions"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "kpi_key", name="uq_analytics_kpi_defs_society_key"
        ),
        Index("ix_analytics_kpi_defs_society_id", "society_id"),
        Index("ix_analytics_kpi_defs_category", "category"),
        Index("ix_analytics_kpi_defs_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kpi_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="count")
    formula_type: Mapped[str] = mapped_column(String(32), nullable=False, default="direct_fact")
    aggregation: Mapped[str] = mapped_column(String(32), nullable=False, default="latest")
    grain: Mapped[str] = mapped_column(String(32), nullable=False, default="society")
    refresh_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="daily")
    roles_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metric_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    numerator_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    denominator_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsDashboardLayout(Base):
    __tablename__ = "analytics_dashboard_layouts"
    __table_args__ = (
        UniqueConstraint(
            "society_id",
            "role",
            "layout_key",
            name="uq_analytics_dashboard_layouts_society_role_key",
        ),
        Index("ix_analytics_dashboard_layouts_society_id", "society_id"),
        Index("ix_analytics_dashboard_layouts_role", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    layout_key: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    widgets_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsDailyFact(Base):
    __tablename__ = "analytics_daily_facts"
    __table_args__ = (
        UniqueConstraint(
            "society_id",
            "grain_date",
            "metric_key",
            "building_id",
            "wing_id",
            name="uq_analytics_daily_facts_grain",
        ),
        Index("ix_analytics_daily_facts_society_date", "society_id", "grain_date"),
        Index("ix_analytics_daily_facts_metric", "society_id", "metric_key", "grain_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grain_date: Mapped[date] = mapped_column(Date, nullable=False)
    building_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    wing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metric_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    dimensions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsMonthlyFact(Base):
    __tablename__ = "analytics_monthly_facts"
    __table_args__ = (
        UniqueConstraint(
            "society_id",
            "year",
            "month",
            "metric_key",
            "building_id",
            "wing_id",
            name="uq_analytics_monthly_facts_grain",
        ),
        Index("ix_analytics_monthly_facts_society", "society_id", "year", "month"),
        Index("ix_analytics_monthly_facts_metric", "society_id", "metric_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    building_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    wing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metric_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    dimensions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsKpiSnapshot(Base):
    __tablename__ = "analytics_kpi_snapshots"
    __table_args__ = (
        Index("ix_analytics_kpi_snapshots_society", "society_id", "as_of"),
        Index("ix_analytics_kpi_snapshots_kpi", "society_id", "kpi_key", "as_of"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kpi_key: Mapped[str] = mapped_column(String(128), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    numerator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    denominator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    building_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsExportJob(Base):
    __tablename__ = "analytics_export_jobs"
    __table_args__ = (
        Index("ix_analytics_export_jobs_society_id", "society_id"),
        Index("ix_analytics_export_jobs_status", "status"),
        Index("ix_analytics_export_jobs_requested_by", "requested_by"),
        Index("ix_analytics_export_jobs_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_key: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    filters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsExportDownload(Base):
    __tablename__ = "analytics_export_downloads"
    __table_args__ = (
        Index("ix_analytics_export_downloads_society_id", "society_id"),
        Index("ix_analytics_export_downloads_job_id", "export_job_id"),
        Index("ix_analytics_export_downloads_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    export_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analytics_export_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    __table_args__ = (
        Index("ix_report_schedules_society_id", "society_id"),
        Index("ix_report_schedules_next_run", "society_id", "next_run_at"),
        Index("ix_report_schedules_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_key: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="csv")
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    filters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recipient_user_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recipient_roles_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ReportScheduleRun(Base):
    __tablename__ = "report_schedule_runs"
    __table_args__ = (
        Index("ix_report_schedule_runs_society_id", "society_id"),
        Index("ix_report_schedule_runs_schedule_id", "schedule_id"),
        Index("ix_report_schedule_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    export_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analytics_export_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AnalyticsUserPreference(Base):
    __tablename__ = "analytics_user_preferences"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "user_id", name="uq_analytics_user_prefs_society_user"
        ),
        Index("ix_analytics_user_prefs_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    favorite_report_keys_json: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    default_filters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    saved_filters_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AnalyticsAccessLog(Base):
    __tablename__ = "analytics_access_logs"
    __table_args__ = (
        Index("ix_analytics_access_logs_society_id", "society_id"),
        Index("ix_analytics_access_logs_user_id", "user_id"),
        Index("ix_analytics_access_logs_action", "action"),
        Index("ix_analytics_access_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
