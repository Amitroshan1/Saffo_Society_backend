from datetime import date

from pydantic import BaseModel


class ClearanceCreate(BaseModel):
    move_out_date: date | None = None


class DocumentCreate(BaseModel):
    doc_type: str
    file_url: str


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
    documents: list[DocumentOut]


class GuardClearanceOut(ClearanceOut):
    flat: str
    resident_name: str
