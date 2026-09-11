"""User SQLAlchemy model — replaces server/models/User.model.js."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Constants.constants import LOCK_MINUTES, MAX_LOGIN_ATTEMPTS
from Database.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
        Index("ix_users_society_id", "society_id"),
        Index("ix_users_flat_id", "flat_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    society_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="RESTRICT"),
        nullable=True,
    )

    flat_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flats.id", ondelete="SET NULL"),
        nullable=True,
    )

    dob: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    blood_group: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    flat_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    wing: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    office_contact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    office_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emergency_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    emergency_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lock_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    otp: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    otp_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def is_locked(self) -> bool:
        if not self.lock_until:
            return False
        lock = self.lock_until
        if lock.tzinfo is None:
            lock = lock.replace(tzinfo=timezone.utc)
        return lock > datetime.now(timezone.utc)

    def inc_login_attempts(self) -> None:
        self.login_attempts += 1
        if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
            self.lock_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)

    def reset_login_attempts(self) -> None:
        self.login_attempts = 0
        self.lock_until = None
