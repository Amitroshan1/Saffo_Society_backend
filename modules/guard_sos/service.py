import math
from datetime import date, datetime, time

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from modules.guard_common.deps import GuardUser
from modules.guard_sos.models import (
    DB_TO_UI,
    IST,
    SOS_CLOSED,
    SOS_OPEN,
    UI_TO_DB,
    SosResolution,
    now_ist,
)
from modules.guard_sos.schemas import Pagination, SosItem, SosListData
from modules.resident.models import Building, Flat, Occupancy, Resident
from modules.sos.models import SosAlert


def _to_item(
    alert: SosAlert,
    resident: Resident,
    flat: Flat,
    building: Building,
    resolution: SosResolution | None,
) -> SosItem:
    return SosItem(
        id=alert.id,
        societyId=alert.society_id,
        residentId=alert.resident_id,
        residentName=resident.full_name,
        residentPhone=resident.phone,
        buildingNo=building.name,
        wingNo=None,
        flatNo=flat.number,
        title=alert.title,
        message=alert.description,
        priority=alert.priority,
        status=DB_TO_UI.get(alert.status, alert.status),
        createdAt=alert.created_at,
        resolvedAt=resolution.resolved_at if resolution else alert.closed_at,
        resolvedBy=resolution.resolved_by if resolution else None,
    )


def base_query(db: Session, society_id: int) -> Query:
    return (
        db.query(SosAlert, Resident, Flat, Building, SosResolution)
        .join(Resident, Resident.id == SosAlert.resident_id)
        .join(Occupancy, Occupancy.id == SosAlert.occupancy_id)
        .join(Flat, Flat.id == Occupancy.flat_id)
        .join(Building, Building.id == Flat.building_id)
        .outerjoin(SosResolution, SosResolution.sos_id == SosAlert.id)
        .filter(SosAlert.society_id == society_id)
    )


def active_items(db: Session, society_id: int) -> list[SosItem]:
    rows = (
        base_query(db, society_id)
        .filter(SosAlert.status == SOS_OPEN)
        .order_by(SosAlert.created_at.desc(), SosAlert.id.desc())
        .all()
    )
    return [_to_item(*row) for row in rows]


def _get_row(db: Session, current_user: GuardUser, sos_id: int):
    row = base_query(db, current_user.society_id).filter(SosAlert.id == sos_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="SOS alert not found")
    return row


def list_sos_alerts(
    db: Session,
    current_user: GuardUser,
    *,
    status_filter: str | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SosListData:
    page_size = min(page_size, 100)
    query = base_query(db, current_user.society_id)

    if status_filter:
        db_status = UI_TO_DB.get(status_filter.strip().lower())
        if not db_status:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(SosAlert.status == db_status)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )

    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        query = query.filter(SosAlert.created_at >= start)

    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        query = query.filter(SosAlert.created_at <= end)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Resident.full_name.ilike(term))
            | (Building.name.ilike(term))
            | (Flat.number.ilike(term))
            | (SosAlert.title.ilike(term))
            | (SosAlert.description.ilike(term))
        )

    sort_map = {
        "createdAt": SosAlert.created_at,
        "resolvedAt": SosAlert.closed_at,
        "flatNo": Flat.number,
        "residentName": Resident.full_name,
    }
    column = sort_map.get(sort_by, SosAlert.created_at)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc()
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size)) if total else 1

    return SosListData(
        items=[_to_item(*row) for row in rows],
        pagination=Pagination(
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            hasNext=page < total_pages,
            hasPrev=page > 1,
        ),
    )


def get_sos_alert(
    db: Session,
    current_user: GuardUser,
    sos_id: int,
) -> SosItem:
    return _to_item(*_get_row(db, current_user, sos_id))


def resolve_sos_alert(
    db: Session,
    current_user: GuardUser,
    sos_id: int,
) -> SosItem:
    alert, resident, flat, building, _ = _get_row(db, current_user, sos_id)
    if alert.status != SOS_OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SOS is already resolved",
        )

    now = now_ist()
    alert.status = SOS_CLOSED
    alert.closed_at = now
    resolution = SosResolution(
        sos_id=alert.id,
        society_id=alert.society_id,
        resolved_by=current_user.id,
        resolved_at=now,
    )
    db.add(resolution)
    db.commit()
    return _to_item(alert, resident, flat, building, resolution)
