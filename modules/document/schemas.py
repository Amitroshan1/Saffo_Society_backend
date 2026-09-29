from datetime import datetime

from pydantic import BaseModel


class Pagination(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool


class DocumentCounts(BaseModel):
    all: int
    security: int
    society: int


class DocumentItem(BaseModel):
    id: int
    title: str
    category: str
    sizeBytes: int
    publishedAt: datetime
    fileName: str
    viewUrl: str
    downloadUrl: str


class DocumentListData(BaseModel):
    counts: DocumentCounts
    items: list[DocumentItem]
    pagination: Pagination
