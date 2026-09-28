from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ParkingSlot(Base):
    __tablename__ = "parking_slots"
    __table_args__ = (UniqueConstraint("society_id", "code", name="uq_slot_society_code"),)

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=True, index=True)
    code = Column(String(30), nullable=False)
    kind = Column(String(20), nullable=False, default="resident")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("society_id", "vehicle_number", name="uq_vehicle_society_number"),)

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("parking_slots.id"), nullable=True, index=True)
    vehicle_number = Column(String(20), nullable=False)
    vehicle_type = Column(String(30), nullable=False)
    make = Column(String(60), nullable=True)
    model = Column(String(60), nullable=True)
    color = Column(String(30), nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    parking_code = Column(String(30), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

    slot = relationship("ParkingSlot")


class VisitorParking(Base):
    __tablename__ = "visitor_parkings"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    slot_id = Column(Integer, ForeignKey("parking_slots.id"), nullable=True, index=True)
    vehicle_number = Column(String(20), nullable=False)
    vehicle_type = Column(String(30), nullable=False)
    purpose = Column(String(120), nullable=True)
    notes = Column(String(255), nullable=True)
    parking_code = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

    slot = relationship("ParkingSlot")