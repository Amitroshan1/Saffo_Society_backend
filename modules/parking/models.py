from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

SLOT_RESIDENT = "resident"
SLOT_VISITOR = "visitor"
SLOT_TYPES = (SLOT_RESIDENT, SLOT_VISITOR)

STATUS_INSIDE = "inside"
STATUS_OUTSIDE = "outside"
STATUS_VACANT = "vacant"
STATUS_OCCUPIED = "occupied"
STATUS_FREE = "free"

RESIDENT_STATUSES = ("all", STATUS_INSIDE, STATUS_OUTSIDE, STATUS_VACANT)
VISITOR_STATUSES = ("all", STATUS_OCCUPIED, STATUS_FREE)


def now_ist() -> datetime:
    return datetime.now(IST)


class ParkingLog(Base):
    __tablename__ = "parking_logs"
    __table_args__ = (
        Index(
            "uq_parking_logs_one_open",
            "society_id",
            "parking_id",
            unique=True,
            postgresql_where=text("exit_time IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    parking_id = Column(Integer, ForeignKey("parking_slots.id"), nullable=False, index=True)
    parking_type = Column(String(20), nullable=False, index=True)
    resident_id = Column(Integer, nullable=True)
    resident_name = Column(String(150), nullable=True)
    visitor_name = Column(String(150), nullable=True)
    visitor_phone = Column(String(20), nullable=True)
    building = Column(String(80), nullable=True)
    wing_no = Column(String(30), nullable=True)
    flat_no = Column(String(50), nullable=True)
    vehicle_number = Column(String(30), nullable=False)
    vehicle_type = Column(String(30), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False, index=True)
    exit_time = Column(DateTime(timezone=True), nullable=True, index=True)
    recorded_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
