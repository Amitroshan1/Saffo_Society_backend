"""LateFeeRule SQLAlchemy model — penalty calculation configuration."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from Database.base import Base


class LateFeeRule(Base):
    __tablename__ = "late_fee_rules"
    __table_args__ = (
        Index("ix_late_fee_rules_society_id", "society_id"),
        Index("ix_late_fee_rules_society_is_active", "society_id", "is_active"),
        Index("ix_late_fee_rules_priority", "priority"),
        Index("ix_late_fee_rules_charge_head_id", "charge_head_id"),
        Index("ix_late_fee_rules_billing_cycle_id", "billing_cycle_id"),
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
    billing_cycle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_cycles.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fixed_amount_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percentage_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_amount_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_penalty_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    apply_on: Mapped[str] = mapped_column(String(32), nullable=False, default="outstanding")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
