from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class Amenity(Base):
    __tablename__ = "amenities"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    is_bookable = Column(Boolean, default=True, nullable=False)
    open_time = Column(String(5), nullable=False, default="06:00")
    close_time = Column(String(5), nullable=False, default="22:00")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    amenity_id = Column(Integer, ForeignKey("amenities.id"), nullable=False, index=True)
    booking_date = Column(Date, nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    guest_count = Column(Integer, nullable=False, default=1)
    purpose = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, default="booked")
    cancel_reason = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

    amenity = relationship("Amenity")