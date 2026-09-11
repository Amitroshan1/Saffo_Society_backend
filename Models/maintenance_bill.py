"""MaintenanceBill & BillLineItem SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class MaintenanceBill(Base):
    __tablename__ = "maintenance_bills"
    __table_args__ = (
        Index("ix_maintenance_bills_society_status", "society_id", "status"),
        Index("ix_maintenance_bills_society_due_date", "society_id", "due_date"),
        Index("ix_maintenance_bills_occupancy_id", "occupancy_id"),
        Index("ix_maintenance_bills_resident_id", "resident_id"),
        Index("ix_maintenance_bills_flat_id", "flat_id"),
        Index("uq_maintenance_bills_society_bill_number", "society_id", "bill_number", unique=True),
        Index("ix_maintenance_bills_financial_year_id", "financial_year_id"),
        Index("ix_maintenance_bills_created_at", "created_at"),
        Index("ix_maintenance_bills_society_id", "society_id"),
        Index("ix_maintenance_bills_billing_cycle_id", "billing_cycle_id"),
        Index("ix_maintenance_bills_accounting_period_id", "accounting_period_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    wing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    flat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flats.id", ondelete="RESTRICT"),
        nullable=False,
    )
    occupancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("occupancies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    billing_cycle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_cycles.id", ondelete="SET NULL"),
        nullable=True,
    )
    financial_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accounting_period_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_periods.id", ondelete="SET NULL"),
        nullable=True,
    )

    bill_number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    penalty_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outstanding_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    write_off_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

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


class BillLineItem(Base):
    __tablename__ = "bill_line_items"
    __table_args__ = (
        Index("ix_bill_line_items_society_id", "society_id"),
        Index("ix_bill_line_items_bill_id", "bill_id"),
        Index("ix_bill_line_items_charge_head_id", "charge_head_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_bills.id", ondelete="CASCADE"),
        nullable=False,
    )
    charge_head_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("charge_heads.id", ondelete="RESTRICT"),
        nullable=False,
    )

    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_penalty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_discount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
