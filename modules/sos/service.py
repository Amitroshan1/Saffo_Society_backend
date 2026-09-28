from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.resident.service import _occupancy_or_404
from modules.sos.crud import get_one, list_for_occupancy
from modules.sos.models import SosAlert
from modules.sos.schemas import SosCreate


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


def create_sos(db: Session, user_id: int, society_id: int | None, data: SosCreate) -> dict:
    resident, occupancy = _occupancy_or_404(db, user_id, society_id)
    row = SosAlert(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        resident_id=resident.id,
        title=data.title.strip(),
        description=data.description.strip(),
        photo_url=data.photo_url,
        category="security",
        priority="critical",
        source="resident",
        status="open",
    )
    db.add(row)
    db.commit()
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