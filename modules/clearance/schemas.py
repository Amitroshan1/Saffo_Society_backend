from datetime import date, datetime

from pydantic import BaseModel


class ClearanceCreate(BaseModel):
    move_out_date: date | None = None


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    file_url: str


class ClearanceOut(BaseModel):
    id: int
    status: str
    dues_clear: bool
    gate_allowed: bool
    move_out_date: date | None
    allowed_at: datetime | None = None
    documents: list[DocumentOut]


class GuardClearanceOut(ClearanceOut):
    flat: str
    resident_name: str
