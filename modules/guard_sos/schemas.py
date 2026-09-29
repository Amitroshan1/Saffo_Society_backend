from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SosItem(BaseModel):
    id: int
    societyId: int
    residentId: int
    residentName: str
    residentPhone: Optional[str] = None
    buildingNo: str
    wingNo: Optional[str] = None
    flatNo: str
    title: str
    message: str
    priority: str
    status: str
    createdAt: datetime
    resolvedAt: Optional[datetime] = None
    resolvedBy: Optional[int] = None


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class SosListData(BaseModel):
    items: list[SosItem]
    pagination: Pagination
