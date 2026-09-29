from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_INSIDE = "inside"
STATUS_EXITED = "exited"

STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_INSIDE,
    STATUS_EXITED,
)


def now_ist() -> datetime:
    return datetime.now(IST)


class Cab(Base):
    __tablename__ = "cabs"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    vehicle_number = Column(String(20), nullable=False, index=True)
    driver_name = Column(String(150), nullable=True)
    cab_service = Column(String(50), nullable=False)
    building_no = Column(String(80), nullable=False)
    wing_no = Column(String(30), nullable=False)
    flat_no = Column(String(50), nullable=False, index=True)
    purpose = Column(String(50), nullable=False)
    photo_path = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default=STATUS_PENDING, index=True)
    recorded_by = Column(Integer, nullable=False, index=True)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
