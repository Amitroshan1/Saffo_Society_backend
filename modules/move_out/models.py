from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

STATUS_PENDING = "pending"
STATUS_READY = "ready"
STATUS_ALLOWED = "allowed"

STATUSES = ("all", STATUS_PENDING, STATUS_READY, STATUS_ALLOWED)


def now_ist() -> datetime:
    return datetime.now(IST)


class MoveOut(Base):
    __tablename__ = "move_out"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    resident_id = Column(Integer, nullable=False, index=True)
    resident_name = Column(String(150), nullable=False)
    flat_no = Column(String(50), nullable=False, index=True)
    building_no = Column(String(80), nullable=False)
    wing_no = Column(String(30), nullable=True)
    move_out_date = Column(Date, nullable=False, index=True)
    leave_license = Column(Boolean, nullable=False, default=False)
    tenant_id_proof = Column(Boolean, nullable=False, default=False)
    owner_confirmation = Column(Boolean, nullable=False, default=False)
    dues_clearance = Column(Boolean, nullable=False, default=False)
    allowed_at = Column(DateTime(timezone=True), nullable=True)
    allowed_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)

    files = relationship(
        "MoveOutFile",
        back_populates="move_out",
        cascade="all, delete-orphan",
        order_by="MoveOutFile.id",
    )


class MoveOutFile(Base):
    __tablename__ = "move_out_files"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    move_out_id = Column(Integer, ForeignKey("move_out.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)

    move_out = relationship("MoveOut", back_populates="files")
