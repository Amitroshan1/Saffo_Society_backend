from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Time

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

STATUS_SCHEDULED = "scheduled"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"

SHIFT_STATUSES = (
    STATUS_SCHEDULED,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
)

ACTION_IN = "in"
ACTION_OUT = "out"

PUNCH_ACTIONS = (
    ACTION_IN,
    ACTION_OUT,
)

ATTENDANCE_PRESENT = "present"
ATTENDANCE_ABSENT = "absent"
ATTENDANCE_SCHEDULED = "scheduled"

ATTENDANCE_STATUSES = (
    ATTENDANCE_PRESENT,
    ATTENDANCE_ABSENT,
    ATTENDANCE_SCHEDULED,
)


def now_ist() -> datetime:
    return datetime.now(IST)


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    guard_user_id = Column(Integer, nullable=False, index=True)
    staff_name = Column(String(150), nullable=False)
    staff_code = Column(String(40), nullable=False)
    gate_name = Column(String(150), nullable=False)
    gate_code = Column(String(30), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Integer, nullable=False, default=100)
    duty_date = Column(Date, nullable=False, index=True)
    shift_type = Column(String(30), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(30), nullable=False, default=STATUS_SCHEDULED, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)


class PunchLog(Base):
    __tablename__ = "punch_logs"

    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, nullable=False, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    guard_user_id = Column(Integer, nullable=False, index=True)
    action = Column(String(10), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    punched_at = Column(DateTime(timezone=True), nullable=False, default=now_ist, index=True)
