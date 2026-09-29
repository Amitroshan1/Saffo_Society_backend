from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeliveryItem(BaseModel):
    id: int
    societyId: int
    courierName: str
    phone: str
    company: str
    trackingId: Optional[str] = None
    buildingNo: str
    wingNo: str
    flatNo: Optional[str] = None
    parcelNote: Optional[str] = None
    photoUrl: Optional[str] = None
    status: str
    receivedBy: Optional[str] = None
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


class DeliveryListData(BaseModel):
    items: list[DeliveryItem]
    pagination: Pagination
