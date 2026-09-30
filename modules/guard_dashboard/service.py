from datetime import date, datetime, time

from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session, joinedload

from modules.cab.models import STATUS_APPROVED as CAB_APPROVED
from modules.cab.models import STATUS_INSIDE as CAB_INSIDE
from modules.cab.models import STATUS_PENDING as CAB_PENDING
from modules.cab.models import Cab
from modules.delivery.models import STATUS_APPROVED as DELIVERY_APPROVED
from modules.delivery.models import STATUS_INSIDE as DELIVERY_INSIDE
from modules.delivery.models import STATUS_PENDING as DELIVERY_PENDING
from modules.delivery.models import Delivery
from modules.facility.models import Booking
from modules.guard_booking.service import confirmed_query
from modules.guard_common.deps import GuardUser
from modules.guard_common.residents import flat_label
from modules.guard_dashboard.schemas import (
    BookingPreview,
    DashboardCounts,
    DashboardData,
    DashboardShift,
    InsideItem,
    MoveOutReadyItem,
    SosPreview,
    WaitingItem,
)
from modules.clearance.models import Clearance
from modules.clearance.service import ALL_CHECKS
from modules.resident.models import Occupancy
from modules.parking.models import SLOT_RESIDENT, SLOT_VISITOR, ParkingLog
from modules.vehicle.models import ParkingSlot, Vehicle
from modules.schedule.models import (
    ACTION_IN,
    IST,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_SCHEDULED,
    PunchLog,
    Shift,
    now_ist,
)
from modules.guard_sos.models import SOS_OPEN
from modules.guard_sos.service import base_query as sos_query
from modules.guard_visitor.models import UI_APPROVED, UI_INSIDE, UI_PENDING, VisitGateEntry
from modules.guard_visitor.service import base_query as visit_query
from modules.guard_visitor.service import status_clause as visit_status
from modules.sos.models import SosAlert
from modules.staff.models import Staff, StaffLog
from modules.visitor.models import Visit

PREVIEW_LIMIT = 5
TYPE_VISITOR = "visitor"
TYPE_DELIVERY = "delivery"
TYPE_CAB = "cab"
TYPE_STAFF = "staff"


def _clock(value: time | str) -> str:
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def _newest(rows: list, stamp):
    return sorted(rows, key=stamp, reverse=True)[:PREVIEW_LIMIT]


def _cab_name(cab: Cab) -> str:
    driver = (cab.driver_name or "").strip()
    return driver or cab.vehicle_number


def _waiting(db: Session, society_id: int) -> list[WaitingItem]:
    visitors = (
        visit_query(db, society_id)
        .filter(visit_status(UI_PENDING))
        .order_by(Visit.created_at.desc(), Visit.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.society_id == society_id, Delivery.status == DELIVERY_PENDING)
        .order_by(Delivery.created_at.desc(), Delivery.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    cabs = (
        db.query(Cab)
        .filter(Cab.society_id == society_id, Cab.status == CAB_PENDING)
        .order_by(Cab.created_at.desc(), Cab.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    items = [
        WaitingItem(
            type=TYPE_VISITOR,
            id=visit.id,
            name=visit.visitor.name,
            flatNo=flat_label(building, flat),
            purpose=visit.purpose or visit.visitor_type,
            createdAt=visit.created_at,
        )
        for visit, _entry, flat, building in visitors
    ]
    items.extend(
        WaitingItem(
            type=TYPE_DELIVERY,
            id=row.id,
            name=row.courier_name,
            flatNo=row.flat_no,
            purpose=row.company,
            createdAt=row.created_at,
        )
        for row in deliveries
    )
    items.extend(
        WaitingItem(
            type=TYPE_CAB,
            id=row.id,
            name=_cab_name(row),
            flatNo=row.flat_no,
            purpose=row.purpose,
            createdAt=row.created_at,
        )
        for row in cabs
    )
    return _newest(items, lambda item: (item.createdAt, item.id))


def _inside(db: Session, society_id: int, today: date) -> list[InsideItem]:
    visitors = (
        visit_query(db, society_id)
        .filter(visit_status(UI_INSIDE))
        .order_by(VisitGateEntry.check_in_time.desc().nulls_last(), Visit.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    deliveries = (
        db.query(Delivery)
        .filter(Delivery.society_id == society_id, Delivery.status == DELIVERY_INSIDE)
        .order_by(Delivery.entry_time.desc().nulls_last(), Delivery.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    cabs = (
        db.query(Cab)
        .filter(Cab.society_id == society_id, Cab.status == CAB_INSIDE)
        .order_by(Cab.entry_time.desc().nulls_last(), Cab.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    staff_rows = (
        db.query(Staff, StaffLog)
        .join(StaffLog, StaffLog.staff_id == Staff.id)
        .filter(
            Staff.society_id == society_id,
            StaffLog.society_id == society_id,
            StaffLog.attendance_date == today,
            StaffLog.check_out.is_(None),
        )
        .order_by(StaffLog.check_in.desc(), Staff.id.desc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    items = [
        InsideItem(
            type=TYPE_VISITOR,
            id=visit.id,
            name=visit.visitor.name,
            flatNo=flat_label(building, flat),
            checkInTime=entry.check_in_time if entry else None,
        )
        for visit, entry, flat, building in visitors
    ]
    items.extend(
        InsideItem(
            type=TYPE_DELIVERY,
            id=row.id,
            name=row.courier_name,
            flatNo=row.flat_no,
            checkInTime=row.entry_time,
        )
        for row in deliveries
    )
    items.extend(
        InsideItem(
            type=TYPE_CAB,
            id=row.id,
            name=_cab_name(row),
            flatNo=row.flat_no,
            checkInTime=row.entry_time,
        )
        for row in cabs
    )
    items.extend(
        InsideItem(
            type=TYPE_STAFF,
            id=person.id,
            name=person.name,
            flatNo=person.flat_no,
            checkInTime=log.check_in,
        )
        for person, log in staff_rows
    )
    floor = datetime.min.replace(tzinfo=IST)
    return sorted(
        items,
        key=lambda item: (item.checkInTime or floor, item.id),
        reverse=True,
    )[:PREVIEW_LIMIT]


def _move_outs(db: Session, society_id: int) -> tuple[int, list[MoveOutReadyItem]]:
    ready = and_(
        Clearance.allowed_at.is_(None),
        Clearance.status == "open",
        ALL_CHECKS,
    )
    query = (
        db.query(Clearance)
        .options(
            joinedload(Clearance.occupancy).joinedload(Occupancy.resident),
            joinedload(Clearance.occupancy).joinedload(Occupancy.flat),
        )
        .filter(Clearance.society_id == society_id, ready)
    )
    total = query.count()
    rows = (
        query.order_by(Clearance.move_out_date.asc().nulls_last(), Clearance.id.asc())
        .limit(PREVIEW_LIMIT)
        .all()
    )
    return total, [
        MoveOutReadyItem(
            id=row.id,
            residentName=row.occupancy.resident.full_name,
            flatNo=row.occupancy.flat.number,
            moveOutDate=row.move_out_date,
        )
        for row in rows
    ]


def _bookings(db: Session, society_id: int, today: date) -> tuple[int, list[BookingPreview]]:
    query = confirmed_query(db, society_id).filter(Booking.booking_date == today)
    rows = query.order_by(Booking.start_time.asc(), Booking.id.asc()).limit(PREVIEW_LIMIT).all()
    return query.count(), [
        BookingPreview(
            id=booking.id,
            facility=amenity.name,
            flatNo=flat_label(building, flat),
            startTime=_clock(booking.start_time),
            endTime=_clock(booking.end_time),
        )
        for booking, amenity, _resident, flat, building in rows
    ]


def _sos(db: Session, society_id: int) -> list[SosPreview]:
    rows = (
        sos_query(db, society_id)
        .filter(SosAlert.status == SOS_OPEN)
        .order_by(SosAlert.created_at.desc(), SosAlert.id.desc())
        .all()
    )
    return [
        SosPreview(
            id=alert.id,
            residentName=resident.full_name,
            flatNo=flat_label(building, flat),
            message=alert.description,
            createdAt=alert.created_at,
        )
        for alert, resident, flat, building, _resolution in rows
    ]


def _parking_in_use(db: Session, society_id: int) -> int:
    open_slot_ids = db.query(ParkingLog.parking_id).filter(
        ParkingLog.society_id == society_id,
        ParkingLog.exit_time.is_(None),
    )
    has_vehicle = exists().where(
        and_(Vehicle.slot_id == ParkingSlot.id, Vehicle.society_id == society_id)
    )
    resident_inside = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == SLOT_RESIDENT,
            ParkingSlot.is_active.is_(True),
            has_vehicle,
            ParkingSlot.id.in_(open_slot_ids),
        )
        .count()
    )
    visitor_filled = (
        db.query(ParkingLog)
        .filter(
            ParkingLog.society_id == society_id,
            ParkingLog.exit_time.is_(None),
            ParkingLog.parking_type == SLOT_VISITOR,
        )
        .count()
    )
    return resident_inside + visitor_filled


def _pick_shift(shifts: list[Shift]) -> Shift | None:
    if not shifts:
        return None
    in_progress = [row for row in shifts if row.status == STATUS_IN_PROGRESS]
    if in_progress:
        return min(in_progress, key=lambda row: (row.start_time, -row.id))
    scheduled = [row for row in shifts if row.status == STATUS_SCHEDULED]
    pool = scheduled or [row for row in shifts if row.status == STATUS_COMPLETED] or shifts
    return min(pool, key=lambda row: (row.start_time, -row.id))


def _shift(db: Session, current_user: GuardUser, today: date) -> DashboardShift | None:
    shifts = (
        db.query(Shift)
        .filter(
            Shift.society_id == current_user.society_id,
            Shift.guard_user_id == current_user.id,
            Shift.duty_date == today,
        )
        .all()
    )
    shift = _pick_shift(shifts)
    if shift is None:
        return None
    punched_in = (
        db.query(PunchLog.id)
        .filter(
            PunchLog.shift_id == shift.id,
            PunchLog.society_id == current_user.society_id,
            PunchLog.guard_user_id == current_user.id,
            PunchLog.action == ACTION_IN,
        )
        .first()
        is not None
    )
    return DashboardShift(
        id=shift.id,
        shiftType=shift.shift_type,
        gateName=shift.gate_name,
        startTime=_clock(shift.start_time),
        endTime=_clock(shift.end_time),
        status=shift.status,
        punchedIn=punched_in,
    )


def _status_count(db: Session, model, society_id: int, status: str) -> int:
    return db.query(model).filter(model.society_id == society_id, model.status == status).count()


def _visit_count(db: Session, society_id: int, ui_status: str) -> int:
    return db.query(Visit).filter(Visit.society_id == society_id, visit_status(ui_status)).count()


def get_dashboard(db: Session, current_user: GuardUser) -> DashboardData:
    society_id = current_user.society_id
    today = now_ist().date()
    visitors_waiting = _visit_count(db, society_id, UI_PENDING)
    deliveries_waiting = _status_count(db, Delivery, society_id, DELIVERY_PENDING)
    cabs_waiting = _status_count(db, Cab, society_id, CAB_PENDING)
    visitors_approved = _visit_count(db, society_id, UI_APPROVED)
    deliveries_approved = _status_count(db, Delivery, society_id, DELIVERY_APPROVED)
    cabs_approved = _status_count(db, Cab, society_id, CAB_APPROVED)
    visitors_inside = _visit_count(db, society_id, UI_INSIDE)
    deliveries_inside = _status_count(db, Delivery, society_id, DELIVERY_INSIDE)
    cabs_inside = _status_count(db, Cab, society_id, CAB_INSIDE)
    staff_inside = (
        db.query(StaffLog)
        .filter(
            StaffLog.society_id == society_id,
            StaffLog.attendance_date == today,
            StaffLog.check_out.is_(None),
        )
        .count()
    )
    move_out_ready, move_out_items = _move_outs(db, society_id)
    bookings_today, booking_items = _bookings(db, society_id, today)
    sos_items = _sos(db, society_id)
    return DashboardData(
        counts=DashboardCounts(
            waitingApproval=visitors_waiting + deliveries_waiting + cabs_waiting,
            approvedAtGate=visitors_approved + deliveries_approved + cabs_approved,
            insideNow=visitors_inside + deliveries_inside + cabs_inside + staff_inside,
            sosActive=len(sos_items),
            moveOutReady=move_out_ready,
            parkingInUse=_parking_in_use(db, society_id),
            bookingsToday=bookings_today,
        ),
        shift=_shift(db, current_user, today),
        waiting=_waiting(db, society_id),
        inside=_inside(db, society_id, today),
        moveOutReadyItems=move_out_items,
        bookings=booking_items,
        sos=sos_items,
    )
