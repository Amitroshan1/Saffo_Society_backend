from datetime import datetime

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class ParkingCounts(BaseModel):
    residentsInside: int
    residentsOutside: int
    visitorFilled: int
    visitorCapacity: int
    visitorFree: int


class ResidentParkingItem(BaseModel):
    id: int
    slotNumber: str
    building: str
    wingNo: str | None = None
    status: str
    residentName: str | None = None
    flatNo: str | None = None
    vehicleNumber: str | None = None
    vehicleType: str | None = None
    entryTime: datetime | None = None


class ResidentParkingListData(BaseModel):
    counts: ParkingCounts
    buildings: list[str]
    items: list[ResidentParkingItem]
    pagination: Pagination


class VisitorParkingItem(BaseModel):
    id: int
    slotNumber: str
    building: str
    wingNo: str | None = None
    status: str
    logId: int | None = None
    visitorName: str | None = None
    phone: str | None = None
    flatBuilding: str | None = None
    flatWingNo: str | None = None
    flatNo: str | None = None
    vehicleNumber: str | None = None
    vehicleType: str | None = None
    entryTime: datetime | None = None


class VisitorParkingListData(BaseModel):
    counts: ParkingCounts
    items: list[VisitorParkingItem]
    pagination: Pagination


class ParkingLogItem(BaseModel):
    id: int
    parkingId: int
    slotNumber: str
    building: str | None = None
    wingNo: str | None = None
    parkingType: str
    residentName: str | None = None
    visitorName: str | None = None
    phone: str | None = None
    flatNo: str | None = None
    vehicleNumber: str
    vehicleType: str
    entryTime: datetime
    exitTime: datetime | None = None
    recordedBy: int


class ParkingLogListData(BaseModel):
    counts: ParkingCounts
    items: list[ParkingLogItem]
    pagination: Pagination


class VisitorEntryRequest(BaseModel):
    visitorName: str
    phone: str
    vehicleNumber: str
    vehicleType: str
    building: str
    wingNo: str | None = None
    flatNo: str
    parkingId: int = Field(..., ge=1)
