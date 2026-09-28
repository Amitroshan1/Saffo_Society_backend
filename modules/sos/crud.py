from sqlalchemy.orm import Session

from modules.sos.models import SosAlert


def list_for_occupancy(db: Session, occupancy_id: int, society_id: int) -> list[SosAlert]:
    return (
        db.query(SosAlert)
        .filter(SosAlert.occupancy_id == occupancy_id, SosAlert.society_id == society_id)
        .order_by(SosAlert.id.desc())
        .all()
    )


def get_one(db: Session, sos_id: int, occupancy_id: int, society_id: int) -> SosAlert | None:
    return (
        db.query(SosAlert)
        .filter(
            SosAlert.id == sos_id,
            SosAlert.occupancy_id == occupancy_id,
            SosAlert.society_id == society_id,
        )
        .first()
    )