from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, UniqueConstraint

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


class GuardProfile(Base):
    __tablename__ = "guard_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_guard_profiles_user"),
        UniqueConstraint("society_id", "staff_code", name="uq_guard_profiles_staff_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    designation = Column(String(80), nullable=False)
    staff_code = Column(String(40), nullable=False)
    gate_name = Column(String(150), nullable=False)
    gate_code = Column(String(30), nullable=False)
    photo_path = Column(String(500), nullable=True)
    joining_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_ist, onupdate=now_ist)
