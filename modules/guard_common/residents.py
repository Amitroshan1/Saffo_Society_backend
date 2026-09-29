from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, contains_eager, joinedload

from modules.resident.models import Building, Flat, Occupancy


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
