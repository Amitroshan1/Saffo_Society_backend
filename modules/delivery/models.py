from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_INSIDE = "inside"
STATUS_EXITED = "exited"
STATUS_HELD = "held"
STATUS_COLLECTED = "collected"

STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_INSIDE,
    STATUS_EXITED,
    STATUS_HELD,
    STATUS_COLLECTED,
)

RECEIVED_BY_GUARD = "received_by_guard"
RECEIVED_BY_RESIDENT = "received_by_resident"


def now_ist() -> datetime:
    return datetime.now(IST)


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    courier_name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    company = Column(String(50), nullable=False)
    tracking_id = Column(String(80), nullable=True)
    building_no = Column(String(80), nullable=False)
    wing_no = Column(String(30), nullable=False)
    flat_no = Column(String(50), nullable=False, index=True)
    parcel_note = Column(Text, nullable=True)
    photo_path = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default=STATUS_PENDING, index=True)
    received_by = Column(String(40), nullable=True)
    recorded_by = Column(Integer, nullable=False, index=True)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
