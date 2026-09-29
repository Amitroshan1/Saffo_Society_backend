import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.guard_common.deps import GuardUser
from .models import (
    ACTION_IN,
    ACTION_OUT,
    ATTENDANCE_ABSENT,
    ATTENDANCE_PRESENT,
    ATTENDANCE_SCHEDULED,
    ATTENDANCE_STATUSES,
    IST,
    SHIFT_STATUSES,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_SCHEDULED,
    PunchLog,
    Shift,
    now_ist,
)
from .schemas import (
    AttendanceItem,
    AttendanceListData,
    Pagination,
    PunchItem,
    PunchListData,
    ShiftItem,
    ShiftListData,
)


def _clock(value) -> str:
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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


def _check_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )


def _to_shift(shift: Shift) -> ShiftItem:
    return ShiftItem(
        id=shift.id,
        dutyDate=shift.duty_date,
        shiftType=shift.shift_type,
        gateName=shift.gate_name,
        gateCode=shift.gate_code,
        staffName=shift.staff_name,
        staffCode=shift.staff_code,
        startTime=_clock(shift.start_time),
        endTime=_clock(shift.end_time),
        status=shift.status,
    )


def _to_punch(log: PunchLog, gate_name: str) -> PunchItem:
    return PunchItem(
        id=log.id,
        shiftId=log.shift_id,
        action=log.action,
        latitude=log.latitude,
        longitude=log.longitude,
        punchedAt=log.punched_at,
        gateName=gate_name,
    )


def _own_shifts(db: Session, current_user: GuardUser):
    return db.query(Shift).filter(
        Shift.society_id == current_user.society_id,
        Shift.guard_user_id == current_user.id,
    )


def _get_own_shift(db: Session, current_user: GuardUser, shift_id: int) -> Shift:
    shift = (
        _own_shifts(db, current_user)
        .filter(Shift.id == shift_id)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


def _assert_inside_gate(shift: Shift, latitude: float, longitude: float) -> None:
    distance = _distance_meters(shift.latitude, shift.longitude, latitude, longitude)
    if distance > shift.radius_meters:
        raise HTTPException(status_code=400, detail="You are outside the assigned gate")


def list_shifts(
    db: Session,
    current_user: GuardUser,
    *,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ShiftListData:
    page_size = min(page_size, 100)
    query = _own_shifts(db, current_user)

    if status_filter:
        clean_status = status_filter.strip().lower()
        if clean_status not in SHIFT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Shift.status == clean_status)

    _check_date_range(date_from, date_to)
    if date_from:
        query = query.filter(Shift.duty_date >= date_from)
    if date_to:
        query = query.filter(Shift.duty_date <= date_to)

    sort_map = {
        "dutyDate": Shift.duty_date,
        "startTime": Shift.start_time,
        "status": Shift.status,
        "gateName": Shift.gate_name,
    }
    column = sort_map.get(sort_by, Shift.duty_date)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc(),
        Shift.id.desc(),
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return ShiftListData(
        items=[_to_shift(row) for row in rows],
        pagination=_pagination(page, page_size, total),
    )


def _attendance_status(shift: Shift, punch_in_at: datetime | None, today: date) -> str:
    if punch_in_at is not None:
        return ATTENDANCE_PRESENT
    if shift.duty_date < today:
        return ATTENDANCE_ABSENT
    return ATTENDANCE_SCHEDULED


def _punch_times(logs: list[PunchLog]) -> tuple[datetime | None, datetime | None]:
    punch_in = [log.punched_at for log in logs if log.action == ACTION_IN]
    punch_out = [log.punched_at for log in logs if log.action == ACTION_OUT]
    return (min(punch_in) if punch_in else None, max(punch_out) if punch_out else None)


def list_attendance(
    db: Session,
    current_user: GuardUser,
    *,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AttendanceListData:
    page_size = min(page_size, 100)
    today = now_ist().date()
    query = _own_shifts(db, current_user)
    has_punch_in = (
        db.query(PunchLog.id)
        .filter(PunchLog.shift_id == Shift.id, PunchLog.action == ACTION_IN)
        .exists()
    )

    if status_filter:
        clean_status = status_filter.strip().lower()
        if clean_status not in ATTENDANCE_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        if clean_status == ATTENDANCE_PRESENT:
            query = query.filter(has_punch_in)
        elif clean_status == ATTENDANCE_ABSENT:
            query = query.filter(Shift.duty_date < today, ~has_punch_in)
        else:
            query = query.filter(Shift.duty_date >= today, ~has_punch_in)

    _check_date_range(date_from, date_to)
    if date_from:
        query = query.filter(Shift.duty_date >= date_from)
    if date_to:
        query = query.filter(Shift.duty_date <= date_to)

    sort_map = {
        "dutyDate": Shift.duty_date,
        "gateName": Shift.gate_name,
    }
    column = sort_map.get(sort_by, Shift.duty_date)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc(),
        Shift.id.desc(),
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    logs_by_shift: dict[int, list[PunchLog]] = defaultdict(list)
    if rows:
        logs = (
            db.query(PunchLog)
            .filter(PunchLog.shift_id.in_([row.id for row in rows]))
            .all()
        )
        for log in logs:
            logs_by_shift[log.shift_id].append(log)

    items = []
    for row in rows:
        punch_in_at, punch_out_at = _punch_times(logs_by_shift.get(row.id, []))
        items.append(
            AttendanceItem(
                shiftId=row.id,
                dutyDate=row.duty_date,
                shiftType=row.shift_type,
                gateName=row.gate_name,
                status=_attendance_status(row, punch_in_at, today),
                punchInAt=punch_in_at,
                punchOutAt=punch_out_at,
            )
        )

    return AttendanceListData(items=items, pagination=_pagination(page, page_size, total))


def list_punches(
    db: Session,
    current_user: GuardUser,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PunchListData:
    page_size = min(page_size, 100)
    query = (
        db.query(PunchLog, Shift.gate_name)
        .join(Shift, Shift.id == PunchLog.shift_id)
        .filter(
            PunchLog.society_id == current_user.society_id,
            PunchLog.guard_user_id == current_user.id,
        )
    )

    _check_date_range(date_from, date_to)
    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        query = query.filter(PunchLog.punched_at >= start)
    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        query = query.filter(PunchLog.punched_at <= end)

    sort_map = {
        "punchedAt": PunchLog.punched_at,
        "action": PunchLog.action,
    }
    column = sort_map.get(sort_by, PunchLog.punched_at)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc(),
        PunchLog.id.desc(),
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return PunchListData(
        items=[_to_punch(log, gate_name) for log, gate_name in rows],
        pagination=_pagination(page, page_size, total),
    )


def _punch(
    db: Session,
    current_user: GuardUser,
    shift_id: int,
    latitude: float,
    longitude: float,
    *,
    action: str,
) -> PunchItem:
    shift = _get_own_shift(db, current_user, shift_id)
    today = now_ist().date()

    if action == ACTION_IN:
        if shift.duty_date != today:
            raise HTTPException(status_code=400, detail="Punch in is allowed only on the duty date")
        if shift.status != STATUS_SCHEDULED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shift is not open for punch in")
        next_status = STATUS_IN_PROGRESS
    else:
        if shift.duty_date != today and shift.duty_date != today - timedelta(days=1):
            raise HTTPException(
                status_code=400,
                detail="Punch out is allowed only on the duty date or the next day",
            )
        if shift.status != STATUS_IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Punch out is allowed only after punch in",
            )
        next_status = STATUS_COMPLETED

    _assert_inside_gate(shift, latitude, longitude)

    log = PunchLog(
        shift_id=shift.id,
        society_id=current_user.society_id,
        guard_user_id=current_user.id,
        action=action,
        latitude=latitude,
        longitude=longitude,
        punched_at=now_ist(),
    )
    shift.status = next_status
    db.add(log)
    db.commit()
    db.refresh(log)
    return _to_punch(log, shift.gate_name)


def punch_in_shift(
    db: Session,
    current_user: GuardUser,
    shift_id: int,
    latitude: float,
    longitude: float,
) -> PunchItem:
    return _punch(db, current_user, shift_id, latitude, longitude, action=ACTION_IN)


def punch_out_shift(
    db: Session,
    current_user: GuardUser,
    shift_id: int,
    latitude: float,
    longitude: float,
) -> PunchItem:
    return _punch(db, current_user, shift_id, latitude, longitude, action=ACTION_OUT)
