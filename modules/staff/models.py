from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

STAFF_REGULAR = "regular"

STATUS_CHECKED_IN = "checked_in"
STATUS_CHECKED_OUT = "checked_out"
STATUS_NOT_MARKED = "not_marked"

STAFF_STATUSES = ("all", STATUS_CHECKED_IN, STATUS_CHECKED_OUT)


def now_ist() -> datetime:
    return datetime.now(IST)


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    role = Column(String(80), nullable=False)
    building_no = Column(String(80), nullable=False)
    wing_no = Column(String(30), nullable=True)
    flat_no = Column(String(50), nullable=False, index=True)
    owner_name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=True, index=True)
    aadhaar = Column(String(20), nullable=True)
    staff_type = Column(String(20), nullable=False, default=STAFF_REGULAR)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)


class StaffLog(Base):
    __tablename__ = "staff_logs"
    __table_args__ = (
        UniqueConstraint(
            "society_id",
            "staff_id",
            "attendance_date",
            name="uq_staff_logs_one_day",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    staff_id = Column(Integer, nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime(timezone=True), nullable=False)
    check_out = Column(DateTime(timezone=True), nullable=True)
    recorded_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
