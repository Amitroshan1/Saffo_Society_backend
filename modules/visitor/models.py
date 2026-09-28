from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="scheduled")
    visitor_type = Column(String(30), nullable=False, default="guest")
    purpose = Column(String(80), nullable=True)
    notes = Column(String(255), nullable=True)
    is_preapproved = Column(Boolean, default=False, nullable=False)
    rejected_by = Column(String(50), nullable=True)
    otp = Column(String(10), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

    visitor = relationship("Visitor")