"""Amenities Booking System SQLAlchemy models (Phase 13)."""

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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Facility(Base):
    __tablename__ = "amenities"
    __table_args__ = (
        UniqueConstraint("society_id", "slug", name="uq_amenities_society_slug"),
        Index("ix_amenities_society_id", "society_id"),
        Index("ix_amenities_status", "status"),
        Index("ix_amenities_category", "category"),
        Index("ix_amenities_is_active", "is_active"),
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
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_per_slot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    security_deposit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    advance_booking_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    cancellation_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    max_bookings_per_resident: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=2
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operating_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    operating_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    available_days: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="0123456")
    rules_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

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


class FacilityBooking(Base):
    __tablename__ = "amenity_bookings"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "booking_number", name="uq_amenity_bookings_society_number"
        ),
        Index("ix_amenity_bookings_society_id", "society_id"),
        Index("ix_amenity_bookings_amenity_id", "amenity_id"),
        Index("ix_amenity_bookings_resident_id", "resident_id"),
        Index("ix_amenity_bookings_user_id", "user_id"),
        Index("ix_amenity_bookings_status", "status"),
        Index("ix_amenity_bookings_booking_date", "booking_date"),
        Index("ix_amenity_bookings_booking_code", "booking_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amenity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("amenities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    booking_number: Mapped[str] = mapped_column(String(32), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    guest_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    purpose: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    security_deposit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    payment_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_required")
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    checked_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    booking_code: Mapped[str] = mapped_column(String(20), nullable=False)

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


class FacilityMaintenanceBlock(Base):
    __tablename__ = "amenity_maintenance_blocks"
    __table_args__ = (
        Index("ix_amenity_maint_blocks_amenity_id", "amenity_id"),
        Index("ix_amenity_maint_blocks_society_id", "society_id"),
        Index("ix_amenity_maint_blocks_start_date", "start_date"),
        Index("ix_amenity_maint_blocks_end_date", "end_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    amenity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("amenities.id", ondelete="CASCADE"),
        nullable=False,
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
