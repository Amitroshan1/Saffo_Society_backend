from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class ShiftItem(BaseModel):
    id: int
    dutyDate: date
    shiftType: str
    gateName: str
    gateCode: str
    staffName: str
    staffCode: str
    startTime: str
    endTime: str
    status: str


class ShiftListData(BaseModel):
    items: list[ShiftItem]
    pagination: Pagination


class AttendanceItem(BaseModel):
    shiftId: int
    dutyDate: date
    shiftType: str
    gateName: str
    status: str
    punchInAt: Optional[datetime] = None
    punchOutAt: Optional[datetime] = None


class AttendanceListData(BaseModel):
    items: list[AttendanceItem]
    pagination: Pagination


class PunchItem(BaseModel):
    id: int
    shiftId: int
    action: str
    latitude: float
    longitude: float
    punchedAt: datetime
    gateName: str


class PunchListData(BaseModel):
    items: list[PunchItem]
    pagination: Pagination


class PunchRequest(BaseModel):
    shiftId: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
