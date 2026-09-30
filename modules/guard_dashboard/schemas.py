from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DashboardCounts(BaseModel):
    waitingApproval: int
    approvedAtGate: int
    insideNow: int
    sosActive: int
    moveOutReady: int
    parkingInUse: int
    bookingsToday: int


class DashboardShift(BaseModel):
    id: int
    shiftType: str
    gateName: str
    startTime: str
    endTime: str
    status: str
    punchedIn: bool


class WaitingItem(BaseModel):
    type: str
    id: int
    name: str
    flatNo: str
    purpose: Optional[str] = None
    createdAt: datetime


class InsideItem(BaseModel):
    type: str
    id: int
    name: str
    flatNo: str
    checkInTime: Optional[datetime] = None


class MoveOutReadyItem(BaseModel):
    id: int
    residentName: str
    flatNo: str
    moveOutDate: Optional[date] = None


class BookingPreview(BaseModel):
    id: int
    facility: str
    flatNo: str
    startTime: str
    endTime: str


class SosPreview(BaseModel):
    id: int
    residentName: str
    flatNo: str
    message: str
    createdAt: datetime


class DashboardData(BaseModel):
    counts: DashboardCounts
    shift: Optional[DashboardShift] = None
    waiting: list[WaitingItem]
    inside: list[InsideItem]
    moveOutReadyItems: list[MoveOutReadyItem]
    bookings: list[BookingPreview]
    sos: list[SosPreview]
