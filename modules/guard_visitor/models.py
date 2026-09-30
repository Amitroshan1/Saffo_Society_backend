from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

# visits.status values shared with the resident visitor module
VISIT_SCHEDULED = "scheduled"
VISIT_WAITING = "waiting"
VISIT_APPROVED = "approved"
VISIT_REJECTED = "rejected"
VISIT_CANCELLED = "cancelled"
VISIT_CHECKED_IN = "checked_in"
VISIT_CHECKED_OUT = "checked_out"

# Status names the Guard Panel shows
UI_PENDING = "pending"
UI_APPROVED = "approved"
UI_INSIDE = "inside"
UI_EXITED = "exited"
UI_REJECTED = "rejected"
UI_CANCELLED = "cancelled"

UI_STATUSES = (UI_PENDING, UI_APPROVED, UI_INSIDE, UI_EXITED, UI_REJECTED, UI_CANCELLED)


def now_ist() -> datetime:
    return datetime.now(IST)


class VisitGateEntry(Base):
    """Gate-side details of a visit (photo, vehicle, entry/exit time) kept next to `visits`."""

    __tablename__ = "visit_gate_entries"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False, unique=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    wing_no = Column(String(30), nullable=True)
    person_count = Column(Integer, nullable=False, default=1)
    vehicle_number = Column(String(30), nullable=True)
    vehicle_type = Column(String(30), nullable=True)
    notify_resident = Column(Boolean, nullable=False, default=True)
    remarks = Column(Text, nullable=True)
    photo_path = Column(String(500), nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_in_time = Column(DateTime(timezone=True), nullable=True)
    check_out_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)

    visit = relationship("Visit")
