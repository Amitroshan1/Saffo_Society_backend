"""Building SQLAlchemy model — society child entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Building(Base):
    __tablename__ = "buildings"
    __table_args__ = (
        Index("ix_buildings_society_id", "society_id"),
        Index("ix_buildings_is_active", "is_active"),
        Index("ix_buildings_status", "status"),
        Index("ix_buildings_society_name", "society_id", "name"),
        Index("uq_buildings_society_code", "society_id", "code", unique=True),
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
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    building_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="operational")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    planned_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    occupied_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vacant_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    built_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_lift: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_parking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
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
