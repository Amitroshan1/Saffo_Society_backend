"""Flat SQLAlchemy model — wing child entity (floor_no only; no Floor table)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Flat(Base):
    __tablename__ = "flats"
    __table_args__ = (
        Index("ix_flats_society_id", "society_id"),
        Index("ix_flats_building_id", "building_id"),
        Index("ix_flats_wing_id", "wing_id"),
        Index("ix_flats_is_active", "is_active"),
        Index("ix_flats_status", "status"),
        Index("ix_flats_floor_no", "floor_no"),
        Index("ix_flats_society_flat_no", "society_id", "flat_no"),
        Index("uq_flats_wing_flat_no", "wing_id", "flat_no", unique=True),
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

    flat_no: Mapped[str] = mapped_column(String(50), nullable=False)
    floor_no: Mapped[str] = mapped_column(String(20), nullable=False)

    flat_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    usage_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="vacant")
    ownership_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    intercom: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
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
