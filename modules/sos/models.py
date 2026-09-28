from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class SosAlert(Base):
    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    photo_url = Column(String(500), nullable=True)
    category = Column(String(30), nullable=False, default="security")
    priority = Column(String(30), nullable=False, default="critical")
    source = Column(String(30), nullable=False, default="resident")
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)