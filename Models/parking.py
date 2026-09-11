"""Parking Management System SQLAlchemy models (Phase 14)."""

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


class ParkingZone(Base):
    __tablename__ = "parking_zones"
    __table_args__ = (
        UniqueConstraint("society_id", "code", name="uq_parking_zones_society_code"),
        Index("ix_parking_zones_society_id", "society_id"),
        Index("ix_parking_zones_zone_type", "zone_type"),
        Index("ix_parking_zones_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zone_type: Mapped[str] = mapped_column(String(32), nullable=False, default="basement")
    floor_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    building_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visitor_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monthly_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visitor_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    additional_vehicle_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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


class ParkingSlot(Base):
    __tablename__ = "parking_slots"
    __table_args__ = (
        UniqueConstraint("society_id", "slot_code", name="uq_parking_slots_society_slot_code"),
        Index("ix_parking_slots_society_id", "society_id"),
        Index("ix_parking_slots_zone_id", "zone_id"),
        Index("ix_parking_slots_status", "status"),
        Index("ix_parking_slots_slot_category", "slot_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parking_zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    slot_category: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    vehicle_types_allowed: Mapped[str] = mapped_column(
        String(120), nullable=False, default="car,bike,scooter,ev"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="available")
    floor_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_covered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_ev_charging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monthly_fee_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_allocation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
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


class ResidentVehicle(Base):
    __tablename__ = "resident_vehicles"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "vehicle_number", name="uq_resident_vehicles_society_vehicle_number"
        ),
        Index("ix_resident_vehicles_society_id", "society_id"),
        Index("ix_resident_vehicles_resident_id", "resident_id"),
        Index("ix_resident_vehicles_vehicle_type", "vehicle_type"),
        Index("ix_resident_vehicles_status", "status"),
        Index("ix_resident_vehicles_parking_code", "parking_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    vehicle_number: Mapped[str] = mapped_column(String(32), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False)
    make: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    parking_code: Mapped[str] = mapped_column(String(20), nullable=False)

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


class ParkingAllocation(Base):
    __tablename__ = "parking_allocations"
    __table_args__ = (
        UniqueConstraint(
            "society_id", "allocation_number", name="uq_parking_allocations_society_number"
        ),
        Index("ix_parking_allocations_society_id", "society_id"),
        Index("ix_parking_allocations_slot_id", "slot_id"),
        Index("ix_parking_allocations_resident_id", "resident_id"),
        Index("ix_parking_allocations_status", "status"),
        Index("ix_parking_allocations_vehicle_id", "vehicle_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parking_slots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resident_vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    allocation_number: Mapped[str] = mapped_column(String(32), nullable=False)
    allocation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="permanent")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    monthly_fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_required"
    )
    allocated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    allocated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transferred_from_allocation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
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


class VisitorParkingLog(Base):
    __tablename__ = "visitor_parking_logs"
    __table_args__ = (
        Index("ix_visitor_parking_logs_society_id", "society_id"),
        Index("ix_visitor_parking_logs_slot_id", "slot_id"),
        Index("ix_visitor_parking_logs_status", "status"),
        Index("ix_visitor_parking_logs_vehicle_number", "vehicle_number"),
        Index("ix_visitor_parking_logs_parking_code", "parking_code"),
        Index("ix_visitor_parking_logs_entry_at", "entry_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parking_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
    )
    visitor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visitors.id", ondelete="SET NULL"),
        nullable=True,
    )
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="SET NULL"),
        nullable=True,
    )
    vehicle_number: Mapped[str] = mapped_column(String(32), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False, default="car")
    parking_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    entry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    exit_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    fee_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_required"
    )
    purpose: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
