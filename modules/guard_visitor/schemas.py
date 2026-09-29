from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VisitorItem(BaseModel):
    id: int
    societyId: int
    name: str
    phone: str
    purpose: Optional[str] = None
    buildingNo: str
    wingNo: Optional[str] = None
    flatNo: str
    personCount: int
    vehicleNumber: Optional[str] = None
    vehicleType: Optional[str] = None
    notifyResident: bool
    preApproved: bool
    remarks: Optional[str] = None
    photoUrl: Optional[str] = None
    status: str
    recordedBy: Optional[int] = None
    checkInTime: Optional[datetime] = None
    checkOutTime: Optional[datetime] = None
    createdAt: datetime


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class VisitorListData(BaseModel):
    items: list[VisitorItem]
    pagination: Pagination


class VisitorRecentData(BaseModel):
    items: list[VisitorItem]
