from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.notification.models import Notification
from modules.resident.service import _occupancy_or_404

ALLOWED_CATEGORIES = ("visitor", "emergency", "parking", "amenity")


def record(
    db: Session,
    *,
    user_id: int,
    society_id: int,
    occupancy_id: int | None,
    category: str,
    title: str,
    body: str,
) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Notification category is not allowed")
    db.add(
        Notification(
            society_id=society_id,
            user_id=user_id,
            occupancy_id=occupancy_id,
            category=category,
            title=title.strip(),
            body=body.strip(),
            is_read=False,
        )
    )


def _out(row: Notification) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "title": row.title,
        "body": row.body,
        "is_read": row.is_read,
        "created_at": row.created_at,
    }


def _scoped(db: Session, user_id: int, society_id: int | None):
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    query = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.society_id == occupancy.society_id,
        Notification.category.in_(ALLOWED_CATEGORIES),
    )
    return occupancy, query


def list_inbox(db: Session, user_id: int, society_id: int | None, category: str | None) -> list:
    _, query = _scoped(db, user_id, society_id)
    if category is not None:
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Notification category is not allowed")
        query = query.filter(Notification.category == category)
    rows = query.order_by(Notification.id.desc()).all()
    return [_out(r) for r in rows]


def get_one(db: Session, user_id: int, society_id: int | None, notification_id: int) -> dict:
    _, query = _scoped(db, user_id, society_id)
    row = query.filter(Notification.id == notification_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _out(row)


def mark_read(db: Session, user_id: int, society_id: int | None, notification_id: int) -> dict:
    _, query = _scoped(db, user_id, society_id)
    row = query.filter(Notification.id == notification_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.is_read = True
    db.commit()
    db.refresh(row)
    return _out(row)


def mark_all_read(db: Session, user_id: int, society_id: int | None) -> dict:
    _, query = _scoped(db, user_id, society_id)
    updated = query.filter(Notification.is_read == False).update(
        {"is_read": True}, synchronize_session=False
    )
    db.commit()
    return {"updated": updated}


def unread_count(db: Session, user_id: int, society_id: int | None) -> dict:
    _, query = _scoped(db, user_id, society_id)
    count = query.filter(Notification.is_read == False).count()
    return {"count": count}
