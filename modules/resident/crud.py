from sqlalchemy.orm import Session, joinedload

from modules.resident.models import Flat, Occupancy, Resident


def get_resident_by_user(db: Session, user_id: int, society_id: int) -> Resident | None:
    return (
        db.query(Resident)
        .filter(Resident.user_id == user_id, Resident.society_id == society_id)
        .first()
    )


def get_active_occupancy(db: Session, resident_id: int, society_id: int) -> Occupancy | None:
    return (
        db.query(Occupancy)
        .options(joinedload(Occupancy.flat).joinedload(Flat.building))
        .filter(
            Occupancy.resident_id == resident_id,
            Occupancy.society_id == society_id,
            Occupancy.is_active == True,
        )
        .first()
    )