from datetime import date, datetime

from pydantic import BaseModel


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class MoveOutCounts(BaseModel):
    all: int
    pending: int
    ready: int
    allowed: int


class MoveOutFileItem(BaseModel):
    id: int
    title: str
    fileName: str
    sizeBytes: int
    viewUrl: str


class MoveOutItem(BaseModel):
    id: int
    residentName: str
    flatNo: str
    buildingNo: str
    wingNo: str | None = None
    moveOutDate: date
    leaveLicense: bool
    tenantIdProof: bool
    ownerConfirmation: bool
    duesClearance: bool
    status: str
    canAllow: bool
    allowedAt: datetime | None = None
    documents: list[MoveOutFileItem]


class MoveOutListData(BaseModel):
    counts: MoveOutCounts
    items: list[MoveOutItem]
    pagination: Pagination
