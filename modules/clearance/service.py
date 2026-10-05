import os
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, exists, not_
from sqlalchemy.orm import Session, joinedload

from modules.clearance.models import Clearance, ClearanceDocument
from modules.clearance.schemas import ClearanceCreate
from modules.guard_common.settings import CLEARANCE_UPLOAD_DIR, MAX_CLEARANCE_DOCUMENT_BYTES
from modules.resident.models import Flat, Occupancy
from modules.resident.service import _occupancy_or_404

RESIDENT_DOC_TYPES = {"leave_license", "tenant_id", "owner_confirm"}
STATUS_OPEN = "open"
STATUS_ALLOWED = "allowed"
DOC_TYPE_ALIASES = {
    "leave_license": "leave_license",
    "leavelicense": "leave_license",
    "tenant_id": "tenant_id",
    "tenantid": "tenant_id",
    "owner_confirm": "owner_confirm",
    "ownerconfirm": "owner_confirm",
    "dues_clear": "dues_clear",
    "duesclear": "dues_clear",
}
IST = ZoneInfo("Asia/Kolkata")
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _document_exists(doc_type: str):
    return exists().where(
        and_(
            ClearanceDocument.clearance_id == Clearance.id,
            ClearanceDocument.doc_type == doc_type,
        )
    )


ALL_CHECKS = and_(
    Clearance.dues_clear.is_(True),
    _document_exists("leave_license"),
    _document_exists("tenant_id"),
    _document_exists("owner_confirm"),
)
NOT_ALL_CHECKS = not_(ALL_CHECKS)


def _normalize_doc_type(value: str) -> str:
    return DOC_TYPE_ALIASES.get(value.strip().replace("-", "_").lower(), "")


def checks_complete(row: Clearance) -> bool:
    have = {d.doc_type for d in (row.documents or [])}
    return bool(row.dues_clear and RESIDENT_DOC_TYPES.issubset(have))


def _out(row: Clearance) -> dict:
    docs = list(row.documents or [])
    have = {d.doc_type for d in docs}
    return {
        "id": row.id,
        "status": row.status,
        "dues_clear": row.dues_clear,
        "gate_allowed": row.dues_clear and RESIDENT_DOC_TYPES.issubset(have),
        "move_out_date": row.move_out_date,
        "allowed_at": row.allowed_at,
        "documents": [
            {"id": d.id, "doc_type": d.doc_type, "file_url": d.file_url} for d in docs
        ],
    }


def _load(db: Session, clearance_id: int) -> Clearance | None:
    return (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(Clearance.id == clearance_id)
        .first()
    )


def _lock(db: Session, clearance_id: int, **filters) -> Clearance | None:
    query = db.query(Clearance).filter(Clearance.id == clearance_id)
    for clause in filters.values():
        query = query.filter(clause)
    return query.with_for_update().first()


def list_mine(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(
            Clearance.occupancy_id == occupancy.id,
            Clearance.society_id == occupancy.society_id,
        )
        .order_by(Clearance.id.desc())
        .all()
    )
    return [_out(r) for r in rows]


def open_case(db: Session, user_id: int, society_id: int | None, data: ClearanceCreate) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    existing = (
        db.query(Clearance)
        .filter(
            Clearance.occupancy_id == occupancy.id,
            Clearance.society_id == occupancy.society_id,
            Clearance.status == STATUS_OPEN,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An open move-out case already exists")
    row = Clearance(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        status=STATUS_OPEN,
        dues_clear=False,
        move_out_date=data.move_out_date,
    )
    db.add(row)
    db.commit()
    loaded = _load(db, row.id)
    return _out(loaded)


def _upload_root() -> Path:
    path = Path(CLEARANCE_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _public_url(filename: str) -> str:
    return "/" + (Path(CLEARANCE_UPLOAD_DIR) / filename).as_posix()


def _remove_clearance_file(stored: str | None) -> None:
    if not stored:
        return
    prefix = "/" + Path(CLEARANCE_UPLOAD_DIR).as_posix().strip("/") + "/"
    if not stored.startswith(prefix):
        return
    name = stored[len(prefix):]
    if not name or "/" in name or "\\" in name:
        return
    root = _upload_root()
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return
    if candidate.is_file():
        candidate.unlink()


def _save_clearance_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG, PNG and WEBP files are allowed",
        )
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if size > MAX_CLEARANCE_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 5 MB")

    filename = f"{uuid.uuid4()}{extension}"
    destination = _upload_root() / filename
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)
    except OSError as exc:
        if destination.is_file():
            destination.unlink()
        raise HTTPException(status_code=500, detail="Failed to save file") from exc
    return _public_url(filename)


def add_document(
    db: Session,
    user_id: int,
    society_id: int | None,
    clearance_id: int,
    file: UploadFile,
    doc_type_value: str,
) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    doc_type = _normalize_doc_type(doc_type_value)
    if doc_type == "dues_clear":
        raise HTTPException(status_code=403, detail="Dues clearance is set by the office")
    if doc_type not in RESIDENT_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Unknown document type")
    row = _lock(
        db,
        clearance_id,
        occupancy=Clearance.occupancy_id == occupancy.id,
        society=Clearance.society_id == occupancy.society_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Clearance not found")
    if row.status != STATUS_OPEN:
        raise HTTPException(status_code=400, detail="Clearance is not open")

    file_url = _save_clearance_file(file)
    current = next((d for d in row.documents if d.doc_type == doc_type), None)
    previous = current.file_url if current else None
    try:
        if current:
            current.file_url = file_url
        else:
            db.add(
                ClearanceDocument(
                    clearance_id=row.id,
                    society_id=row.society_id,
                    doc_type=doc_type,
                    file_url=file_url,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        _remove_clearance_file(file_url)
        raise
    if previous and previous != file_url:
        _remove_clearance_file(previous)
    return _out(_load(db, row.id))


def mark_dues(db: Session, society_id: int | None, clearance_id: int) -> dict:
    if society_id is None:
        raise HTTPException(status_code=403, detail="No society selected")
    row = _lock(db, clearance_id, society=Clearance.society_id == society_id)
    if not row:
        raise HTTPException(status_code=404, detail="Clearance not found")
    if row.status != STATUS_OPEN:
        raise HTTPException(status_code=400, detail="Clearance is not open")
    row.dues_clear = True
    db.commit()
    return _out(_load(db, row.id))


def allow_exit(db: Session, society_id: int, clearance_id: int, guard_user_id: int) -> Clearance:
    row = _lock(db, clearance_id, society=Clearance.society_id == society_id)
    if not row:
        raise HTTPException(status_code=404, detail="Move-out not found")
    if row.status != STATUS_OPEN or row.allowed_at is not None:
        raise HTTPException(status_code=409, detail="Move-out is already allowed")
    if not checks_complete(row):
        raise HTTPException(
            status_code=409,
            detail="Allow to go is available only when every check is Yes",
        )
    row.allowed_at = datetime.now(IST)
    row.allowed_by = guard_user_id
    row.status = STATUS_ALLOWED
    db.commit()
    return row


def list_for_guard(db: Session, society_id: int | None) -> list:
    if society_id is None:
        raise HTTPException(status_code=403, detail="No society selected")
    rows = (
        db.query(Clearance)
        .options(
            joinedload(Clearance.documents),
            joinedload(Clearance.occupancy).joinedload(Occupancy.flat).joinedload(Flat.building),
            joinedload(Clearance.occupancy).joinedload(Occupancy.resident),
        )
        .filter(Clearance.society_id == society_id)
        .order_by(Clearance.id.desc())
        .all()
    )
    result = []
    for row in rows:
        item = _out(row)
        flat = row.occupancy.flat
        item["flat"] = f"{flat.building.name}-{flat.number}"
        item["resident_name"] = row.occupancy.resident.full_name
        result.append(item)
    return result
