from datetime import date, time
from typing import Optional

from pydantic import BaseModel


class BookingItem(BaseModel):
    id: int
    bookingCode: str
    residentName: str
    buildingNo: str
    flatNo: str
    facility: str
    bookingDate: date
    startTime: time
    endTime: time
    guestCount: int
    purpose: Optional[str] = None
    status: str


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class BookingCounts(BaseModel):
    today: int
    upcoming: int
    history: int


class BookingListData(BaseModel):
    items: list[BookingItem]
    counts: BookingCounts
    pagination: Pagination
