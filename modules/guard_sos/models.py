from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

# sos_alerts.status values shared with the resident SOS module
SOS_OPEN = "open"
SOS_CLOSED = "closed"

# Status names the Guard Panel shows
UI_ACTIVE = "active"
UI_RESOLVED = "resolved"

UI_TO_DB = {
    UI_ACTIVE: SOS_OPEN,
    UI_RESOLVED: SOS_CLOSED,
}
DB_TO_UI = {db_status: ui_status for ui_status, db_status in UI_TO_DB.items()}


def now_ist() -> datetime:
    return datetime.now(IST)


class SosResolution(Base):
    """Which guard resolved an SOS; residents closing their own SOS leave no row here."""

    __tablename__ = "sos_resolutions"

    id = Column(Integer, primary_key=True, index=True)
    sos_id = Column(Integer, ForeignKey("sos_alerts.id"), nullable=False, unique=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
