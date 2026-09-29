import math
import re
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, aliased

from modules.guard_common.deps import GuardUser
from modules.staff.models import (
    STAFF_STATUSES,
    STATUS_CHECKED_IN,
    STATUS_CHECKED_OUT,
    STATUS_NOT_MARKED,
    Staff,
    StaffLog,
    now_ist,
)
from modules.staff.schemas import Pagination, StaffCounts, StaffItem, StaffListData

STAFF_SORTS = {
    "name": Staff.name,
    "role": Staff.role,
    "buildingNo": Staff.building_no,
    "wingNo": Staff.wing_no,
    "flatNo": Staff.flat_no,
    "worksAt": Staff.flat_no,
    "ownerName": Staff.owner_name,
    "phone": Staff.phone,
}


def _pagination(page: int, page_size: int, total: int) -> Pagination:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return Pagination(
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


def _mask_aadhaar(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return None
    if len(digits) < 4:
        return "XXXX-XXXX-XXXX"
    return f"XXXX-XXXX-{digits[-4:]}"


def _window(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    if date_from is None and date_to is None:
        today = now_ist().date()
        return today, today
    if date_from is None:
        date_from = date_to
    if date_to is None:
        date_to = date_from
    if date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )
    return date_from, date_to


def _direction(column, sort_order: str):
    if sort_order == "asc":
        return column.asc().nulls_last()
    return column.desc().nulls_last()


def _status(log: StaffLog | None) -> str:
    if log is None:
        return STATUS_NOT_MARKED
    if log.check_out is None:
        return STATUS_CHECKED_IN
    return STATUS_CHECKED_OUT


def _to_item(person: Staff, log: StaffLog | None) -> StaffItem:
    return StaffItem(
        id=person.id,
        name=person.name,
        role=person.role,
        buildingNo=person.building_no,
        wingNo=person.wing_no,
        flatNo=person.flat_no,
        ownerName=person.owner_name,
        phone=person.phone,
        aadhaar=_mask_aadhaar(person.aadhaar),
        status=_status(log),
        checkIn=log.check_in if log is not None else None,
        checkOut=log.check_out if log is not None else None,
    )


def _person(db: Session, society_id: int, staff_id: int) -> Staff:
    person = (
        db.query(Staff)
        .filter(Staff.id == staff_id, Staff.society_id == society_id)
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Staff not found")
    return person


def _log_on(db: Session, society_id: int, staff_id: int, day: date) -> StaffLog | None:
    return (
        db.query(StaffLog)
        .filter(
            StaffLog.society_id == society_id,
            StaffLog.staff_id == staff_id,
            StaffLog.attendance_date == day,
        )
        .first()
    )


def _roster(db: Session, society_id: int, date_from: date, date_to: date):
    latest_dates = (
        db.query(
            StaffLog.staff_id.label("staff_id"),
            func.max(StaffLog.attendance_date).label("attendance_date"),
        )
        .filter(
            StaffLog.society_id == society_id,
            StaffLog.attendance_date >= date_from,
            StaffLog.attendance_date <= date_to,
        )
        .group_by(StaffLog.staff_id)
        .subquery()
    )
    log = aliased(StaffLog)
    query = (
        db.query(Staff, log)
        .outerjoin(latest_dates, latest_dates.c.staff_id == Staff.id)
        .outerjoin(
            log,
            and_(
                log.staff_id == Staff.id,
                log.society_id == society_id,
                log.attendance_date == latest_dates.c.attendance_date,
            ),
        )
        .filter(Staff.society_id == society_id)
    )
    return query, log


def _counts(db: Session, society_id: int, date_from: date, date_to: date) -> StaffCounts:
    everyone = db.query(Staff).filter(Staff.society_id == society_id).count()
    inside_query, inside_log = _roster(db, society_id, date_from, date_to)
    checked_in = inside_query.filter(
        inside_log.id.isnot(None),
        inside_log.check_out.is_(None),
    ).count()
    outside_query, outside_log = _roster(db, society_id, date_from, date_to)
    checked_out = outside_query.filter(outside_log.check_out.isnot(None)).count()
    return StaffCounts(all=everyone, checkedIn=checked_in, checkedOut=checked_out)


def list_staff(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    status_filter: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> StaffListData:
    page_size = min(page_size, 100)
    clean_status = (status_filter or "all").strip().lower()
    if clean_status not in STAFF_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    order = (sort_order or "asc").strip().lower()
    if order not in ("asc", "desc"):
        order = "asc"

    start, end = _window(date_from, date_to)
    society_id = current_user.society_id
    query, log = _roster(db, society_id, start, end)

    if clean_status == STATUS_CHECKED_IN:
        query = query.filter(log.id.isnot(None), log.check_out.is_(None))
    elif clean_status == STATUS_CHECKED_OUT:
        query = query.filter(log.check_out.isnot(None))

    if search and search.strip():
        term = f"%{search.strip()}%"
        digits = re.sub(r"\D", "", search)
        clauses = [
            Staff.name.ilike(term),
            Staff.role.ilike(term),
            Staff.building_no.ilike(term),
            Staff.wing_no.ilike(term),
            Staff.flat_no.ilike(term),
            Staff.owner_name.ilike(term),
            Staff.phone.ilike(term),
            Staff.aadhaar.ilike(term),
        ]
        if digits:
            clauses.append(Staff.phone.ilike(f"%{digits}%"))
            clauses.append(Staff.aadhaar.ilike(f"%{digits}%"))
        query = query.filter(or_(*clauses))

    if sort_by == "status":
        rank = case(
            (and_(log.id.isnot(None), log.check_out.is_(None)), 0),
            (log.id.isnot(None), 1),
            else_=2,
        )
        primary = rank.asc() if order == "asc" else rank.desc()
        query = query.order_by(primary, Staff.name.asc(), Staff.id.asc())
    elif sort_by == "checkIn":
        query = query.order_by(_direction(log.check_in, order), Staff.name.asc(), Staff.id.asc())
    elif sort_by == "checkOut":
        query = query.order_by(_direction(log.check_out, order), Staff.name.asc(), Staff.id.asc())
    else:
        column = STAFF_SORTS.get(sort_by, Staff.name)
        query = query.order_by(_direction(column, order), Staff.id.asc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return StaffListData(
        counts=_counts(db, society_id, start, end),
        items=[_to_item(person, day_log) for person, day_log in rows],
        pagination=_pagination(page, page_size, total),
    )


def enter_staff(db: Session, current_user: GuardUser, staff_id: int) -> StaffItem:
    person = _person(db, current_user.society_id, staff_id)
    today = now_ist().date()
    existing = _log_on(db, current_user.society_id, person.id, today)
    if existing and existing.check_out is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff is already checked in")
    if existing and existing.check_out is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff has already checked out")

    now = now_ist()
    log = StaffLog(
        society_id=current_user.society_id,
        staff_id=person.id,
        attendance_date=today,
        check_in=now,
        recorded_by=current_user.id,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _to_item(person, log)


def exit_staff(db: Session, current_user: GuardUser, staff_id: int) -> StaffItem:
    person = _person(db, current_user.society_id, staff_id)
    today = now_ist().date()
    log = _log_on(db, current_user.society_id, person.id, today)
    if not log:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff has not checked in")
    if log.check_out is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff has already checked out")

    log.check_out = now_ist()
    db.commit()
    db.refresh(log)
    return _to_item(person, log)
