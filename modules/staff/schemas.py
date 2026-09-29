from datetime import datetime

from pydantic import BaseModel


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class StaffCounts(BaseModel):
    all: int
    checkedIn: int
    checkedOut: int


class StaffItem(BaseModel):
    id: int
    name: str
    role: str
    buildingNo: str
    wingNo: str | None = None
    flatNo: str
    ownerName: str
    phone: str | None = None
    aadhaar: str | None = None
    status: str
    checkIn: datetime | None = None
    checkOut: datetime | None = None


class StaffListData(BaseModel):
    counts: StaffCounts
    items: list[StaffItem]
    pagination: Pagination
