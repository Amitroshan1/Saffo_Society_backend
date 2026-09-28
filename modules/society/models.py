from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from app.database import Base

class Society(Base):
    __tablename__ = "societies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    registration_number = Column(String(80), unique=True, nullable=False)
    society_type = Column(String(50), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(80), nullable=False)
    state = Column(String(80), nullable=False)
    pincode = Column(String(10), nullable=False)
    email = Column(String(255), nullable=False)
    contact_number = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False,
    )

