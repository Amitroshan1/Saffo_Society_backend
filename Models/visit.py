"""Visit SQLAlchemy model — single gate entry/exit event."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_society_id", "society_id"),
        Index("ix_visits_building_id", "building_id"),
        Index("ix_visits_wing_id", "wing_id"),
        Index("ix_visits_flat_id", "flat_id"),
        Index("ix_visits_occupancy_id", "occupancy_id"),
        Index("ix_visits_visitor_id", "visitor_id"),
        Index("ix_visits_status", "status"),
        Index("ix_visits_visitor_type", "visitor_type"),
        Index("ix_visits_expected_at", "expected_at"),
        Index("ix_visits_check_in_time", "check_in_time"),
        Index("ix_visits_society_status_expected", "society_id", "status", "expected_at"),
        Index("ix_visits_society_created_at", "society_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.id", ondelete="RESTRICT"), nullable=False
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="RESTRICT"), nullable=False
    )
    wing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wings.id", ondelete="RESTRICT"), nullable=False
    )
    flat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flats.id", ondelete="RESTRICT"), nullable=False
    )
    occupancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("occupancies.id", ondelete="RESTRICT"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="RESTRICT"), nullable=False
    )

    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    visitor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    pass_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    gate_in_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    gate_out_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    vehicle_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    number_of_people: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    qr_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    otp: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_preapproved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
