from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Clearance(Base):
    __tablename__ = "clearances"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    occupancy_id = Column(Integer, ForeignKey("occupancies.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open")
    dues_clear = Column(Boolean, default=False, nullable=False)
    move_out_date = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

    occupancy = relationship("Occupancy")
    documents = relationship("ClearanceDocument")


class ClearanceDocument(Base):
    __tablename__ = "clearance_documents"

    id = Column(Integer, primary_key=True, index=True)
    clearance_id = Column(Integer, ForeignKey("clearances.id"), nullable=False, index=True)
    society_id = Column(Integer, ForeignKey("societies.id"), nullable=False, index=True)
    doc_type = Column(String(30), nullable=False)
    file_url = Column(String(500), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )
