"""Occupancy SQLAlchemy model — time-bounded flat assignment."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Occupancy(Base):
    __tablename__ = "occupancies"
    __table_args__ = (
        Index("ix_occupancies_society_id", "society_id"),
        Index("ix_occupancies_building_id", "building_id"),
        Index("ix_occupancies_wing_id", "wing_id"),
        Index("ix_occupancies_flat_id", "flat_id"),
        Index("ix_occupancies_resident_id", "resident_id"),
        Index("ix_occupancies_status", "status"),
        Index("ix_occupancies_role", "role"),
        Index("ix_occupancies_flat_status", "flat_id", "status"),
        Index("ix_occupancies_resident_status", "resident_id", "status"),
        Index("ix_occupancies_society_move_in", "society_id", "move_in_date"),
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
    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    move_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    move_out_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ended_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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
