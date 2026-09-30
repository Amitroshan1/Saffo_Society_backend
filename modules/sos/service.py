import os
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from modules.guard_common.settings import MAX_SOS_PHOTO_BYTES, SOS_UPLOAD_DIR
from modules.resident.service import _occupancy_or_404
from modules.sos.crud import get_one, list_for_occupancy
from modules.sos.models import SosAlert

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _out(row: SosAlert) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "photo_url": row.photo_url,
        "category": row.category,
        "priority": row.priority,
        "source": row.source,
        "status": row.status,
        "occupancy_id": row.occupancy_id,
    }


def _upload_root() -> Path:
    path = Path(SOS_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _public_url(filename: str) -> str:
    return "/" + (Path(SOS_UPLOAD_DIR) / filename).as_posix()


def _remove_sos_photo(stored: str | None) -> None:
    if not stored:
        return
    prefix = "/" + Path(SOS_UPLOAD_DIR).as_posix().strip("/") + "/"
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


def _save_sos_photo(file: UploadFile | None) -> str | None:
    if file is None or not file.filename:
        return None
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG and WEBP images are allowed",
        )
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if size > MAX_SOS_PHOTO_BYTES:
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


def create_sos(
    db: Session,
    user_id: int,
    society_id: int | None,
    title: str,
    description: str,
    file: UploadFile | None,
) -> dict:
    resident, occupancy = _occupancy_or_404(db, user_id, society_id)
    clean_title = title.strip()
    clean_description = description.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not clean_description:
        raise HTTPException(status_code=400, detail="Description is required")
    photo_url = _save_sos_photo(file)
    row = SosAlert(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        resident_id=resident.id,
        title=clean_title,
        description=clean_description,
        photo_url=photo_url,
        category="security",
        priority="critical",
        source="resident",
        status="open",
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _remove_sos_photo(photo_url)
        raise
    db.refresh(row)
    return _out(row)


def list_sos(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    return [_out(r) for r in list_for_occupancy(db, occupancy.id, occupancy.society_id)]


def close_sos(db: Session, user_id: int, society_id: int | None, sos_id: int) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    row = get_one(db, sos_id, occupancy.id, occupancy.society_id)
    if not row:
        raise HTTPException(status_code=404, detail="SOS not found")
    if row.status == "closed":
        raise HTTPException(status_code=400, detail="SOS already closed")
    row.status = "closed"
    row.closed_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    db.commit()
    db.refresh(row)
    return _out(row)