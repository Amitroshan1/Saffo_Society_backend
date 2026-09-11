"""Wing SQLAlchemy model — building child entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class Wing(Base):
    __tablename__ = "wings"
    __table_args__ = (
        Index("ix_wings_society_id", "society_id"),
        Index("ix_wings_building_id", "building_id"),
        Index("ix_wings_is_active", "is_active"),
        Index("ix_wings_status", "status"),
        Index("ix_wings_society_name", "society_id", "name"),
        Index("uq_wings_building_code", "building_id", "code", unique=True),
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

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    short_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    wing_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="operational")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)

    total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_flats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    elevator_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    emergency_stair_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
