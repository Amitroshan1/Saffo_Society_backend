from sqlalchemy.orm import Session, joinedload

from modules.visitor.models import Visit, Visitor


def get_or_create_visitor(db: Session, society_id: int, name: str, phone: str) -> Visitor:
    row = (
        db.query(Visitor)
        .filter(Visitor.society_id == society_id, Visitor.phone == phone)
        .first()
    )
    if row:
        row.name = name
        return row
    row = Visitor(society_id=society_id, name=name, phone=phone)
    db.add(row)
    db.flush()
    return row


def list_visits(
    db: Session,
    occupancy_id: int,
    society_id: int,
    status: str | None,
    search: str | None,
) -> list[Visit]:
    q = (
        db.query(Visit)
        .options(joinedload(Visit.visitor))
        .filter(Visit.occupancy_id == occupancy_id, Visit.society_id == society_id)
    )
    if status:
        q = q.filter(Visit.status == status)
    if search:
        q = q.join(Visitor).filter(Visitor.name.ilike(f"%{search}%"))
    return q.order_by(Visit.id.desc()).all()


def get_visit(db: Session, visit_id: int, occupancy_id: int, society_id: int) -> Visit | None:
    return (
        db.query(Visit)
        .options(joinedload(Visit.visitor))
        .filter(
            Visit.id == visit_id,
            Visit.occupancy_id == occupancy_id,
            Visit.society_id == society_id,
        )
        .first()
    )