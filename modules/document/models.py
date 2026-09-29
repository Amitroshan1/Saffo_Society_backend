from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base

IST = ZoneInfo("Asia/Kolkata")

CATEGORY_SECURITY = "security"
CATEGORY_SOCIETY = "society"

CATEGORIES = ("all", CATEGORY_SECURITY, CATEGORY_SOCIETY)


def now_ist() -> datetime:
    return datetime.now(IST)


class GateDocument(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    society_id = Column(Integer, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(30), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    uploaded_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_ist)
