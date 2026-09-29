from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager, joinedload

from modules.guard_common.deps import GuardUser
from modules.resident.models import Building, Flat, Occupancy

RESULT_LIMIT = 20


class FlatSuggestion(BaseModel):
    id: int
    building: str
    flat: str
    label: str


def flat_label(building: Building | None, flat: Flat | None) -> str:
    if building is None or flat is None:
        return ""
    return f"{building.name}-{flat.number}"


def find_active_occupancy(db: Session, society_id: int, building: str, flat: str) -> Occupancy:
    """Guard types building + flat at the gate; resolve it to the resident living there."""
    row = (
        db.query(Occupancy)
        .join(Flat, Flat.id == Occupancy.flat_id)
        .join(Building, Building.id == Flat.building_id)
        .options(
            contains_eager(Occupancy.flat).contains_eager(Flat.building),
            joinedload(Occupancy.resident),
        )
        .filter(
            Occupancy.society_id == society_id,
            Occupancy.is_active.is_(True),
            func.lower(Building.name) == building.strip().lower(),
            func.lower(Flat.number) == flat.strip().lower(),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No active resident found for this flat")
    return row


def search_flats(db: Session, current_user: GuardUser, search: str | None) -> list[FlatSuggestion]:
    query = (
        db.query(Flat, Building)
        .join(Building, Building.id == Flat.building_id)
        .filter(
            Flat.society_id == current_user.society_id,
            Building.society_id == current_user.society_id,
        )
    )

    term = (search or "").strip()
    if term:
        label = func.concat(Building.name, "-", Flat.number)
        compact = func.concat(Building.name, Flat.number)
        pieces = term.split("-", 1)
        conditions = [
            label.ilike(f"%{term}%"),
            compact.ilike(f"%{term.replace(' ', '')}%"),
            Building.name.ilike(f"%{term}%"),
            Flat.number.ilike(f"%{term}%"),
        ]
        if len(pieces) == 2 and pieces[0].strip() and pieces[1].strip():
            conditions.append(
                (Building.name.ilike(f"%{pieces[0].strip()}%"))
                & (Flat.number.ilike(f"%{pieces[1].strip()}%"))
            )
        query = query.filter(or_(*conditions))

    rows = query.order_by(Building.name.asc(), Flat.number.asc()).limit(RESULT_LIMIT).all()
    return [
        FlatSuggestion(
            id=flat.id,
            building=building.name,
            flat=flat.number,
            label=flat_label(building, flat),
        )
        for flat, building in rows
    ]
