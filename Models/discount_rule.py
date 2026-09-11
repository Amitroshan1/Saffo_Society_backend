"""DiscountRule SQLAlchemy model — discount configuration / eligibility."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class DiscountRule(Base):
    __tablename__ = "discount_rules"
    __table_args__ = (
        Index("ix_discount_rules_society_id", "society_id"),
        Index("ix_discount_rules_society_is_active", "society_id", "is_active"),
        Index("ix_discount_rules_resident_id", "resident_id"),
        Index("ix_discount_rules_effective", "effective_from", "effective_to"),
        Index("ix_discount_rules_charge_head_id", "charge_head_id"),
        Index("ix_discount_rules_occupancy_id", "occupancy_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    charge_head_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("charge_heads.id", ondelete="SET NULL"),
        nullable=True,
    )
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.id", ondelete="SET NULL"),
        nullable=True,
    )
    occupancy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("occupancies.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fixed_amount_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percentage_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="society")
    one_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

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
