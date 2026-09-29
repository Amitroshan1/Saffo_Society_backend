from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CabItem(BaseModel):
    id: int
    societyId: int
    vehicleNumber: str
    driverName: Optional[str] = None
    cabService: str
    buildingNo: str
    wingNo: str
    flatNo: str
    purpose: str
    photoUrl: Optional[str] = None
    status: str
    recordedBy: int
    entryTime: Optional[datetime] = None
    exitTime: Optional[datetime] = None
    createdAt: datetime


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class CabListData(BaseModel):
    items: list[CabItem]
    pagination: Pagination
