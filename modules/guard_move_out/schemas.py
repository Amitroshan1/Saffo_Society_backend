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


class MoveOutDocumentItem(BaseModel):
    id: int
    docType: str
    fileUrl: str


class MoveOutItem(BaseModel):
    id: int
    residentName: str
    flatNo: str
    buildingNo: str
    moveOutDate: date | None = None
    leaveLicense: bool
    tenantIdProof: bool
    ownerConfirmation: bool
    duesClearance: bool
    status: str
    canAllow: bool
    allowedAt: datetime | None = None
    documents: list[MoveOutDocumentItem]


class MoveOutListData(BaseModel):
    counts: MoveOutCounts
    items: list[MoveOutItem]
    pagination: Pagination
