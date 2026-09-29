import math
import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from modules.facility.models import Amenity, Booking
from modules.guard_booking.schemas import BookingCounts, BookingItem, BookingListData, Pagination
from modules.guard_common.deps import GuardUser
from modules.resident.models import Building, Flat, Occupancy, Resident

IST = ZoneInfo("Asia/Kolkata")

# bookings.status value written by the resident facility module
BOOKING_CONFIRMED = "booked"
# Status name the Guard Panel shows for a confirmed booking
UI_APPROVED = "approved"

VIEW_TODAY = "today"
VIEW_UPCOMING = "upcoming"
VIEW_DATE = "date"
VIEW_HISTORY = "history"
VIEWS = (VIEW_TODAY, VIEW_UPCOMING, VIEW_DATE, VIEW_HISTORY)

CODE_PREFIX = "BK-"


def today_ist() -> date:
    return datetime.now(IST).date()


def booking_code(booking_id: int) -> str:
    return f"{CODE_PREFIX}{booking_id:05d}"


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _to_item(
    booking: Booking,
    amenity: Amenity,
    resident: Resident,
    flat: Flat,
    building: Building,
) -> BookingItem:
    return BookingItem(
        id=booking.id,
        bookingCode=booking_code(booking.id),
        residentName=resident.full_name,
        buildingNo=building.name,
        flatNo=flat.number,
        facility=amenity.name,
        bookingDate=booking.booking_date,
        startTime=_clock(booking.start_time),
        endTime=_clock(booking.end_time),
        guestCount=booking.guest_count,
        purpose=booking.purpose,
        status=UI_APPROVED,
    )


def confirmed_query(db: Session, society_id: int) -> Query:
    return (
        db.query(Booking, Amenity, Resident, Flat, Building)
        .join(Amenity, Amenity.id == Booking.amenity_id)
        .join(Occupancy, Occupancy.id == Booking.occupancy_id)
        .join(Resident, Resident.id == Occupancy.resident_id)
        .join(Flat, Flat.id == Occupancy.flat_id)
        .join(Building, Building.id == Flat.building_id)
        .filter(Booking.society_id == society_id, Booking.status == BOOKING_CONFIRMED)
    )


def _count_query(db: Session, society_id: int) -> Query:
    return db.query(Booking).filter(
        Booking.society_id == society_id,
        Booking.status == BOOKING_CONFIRMED,
    )


def _counts(db: Session, society_id: int, today: date) -> BookingCounts:
    confirmed = _count_query(db, society_id)
    return BookingCounts(
        today=confirmed.filter(Booking.booking_date == today).count(),
        upcoming=confirmed.filter(Booking.booking_date > today).count(),
        history=confirmed.filter(Booking.booking_date < today).count(),
    )


def _apply_view(query: Query, view: str, today: date, on_date: date | None) -> Query:
    if view == VIEW_TODAY:
        return query.filter(Booking.booking_date == today)
    if view == VIEW_UPCOMING:
        return query.filter(Booking.booking_date > today)
    if view == VIEW_DATE:
        return query.filter(Booking.booking_date == on_date)
    return query.filter(Booking.booking_date < today)


def _search(query: Query, search: str) -> Query:
    clean = search.strip()
    term = f"%{clean}%"
    condition = (
        (Amenity.name.ilike(term))
        | (Resident.full_name.ilike(term))
        | (Building.name.ilike(term))
        | (Flat.number.ilike(term))
    )
    code = re.fullmatch(rf"(?:{CODE_PREFIX})?0*(\d+)", clean, flags=re.IGNORECASE)
    if code:
        condition = condition | (Booking.id == int(code.group(1)))
    return query.filter(condition)


def list_bookings(
    db: Session,
    current_user: GuardUser,
    *,
    view: str,
    on_date: date | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> BookingListData:
    clean_view = (view or VIEW_TODAY).strip().lower()
    if clean_view not in VIEWS:
        raise HTTPException(status_code=400, detail="Invalid view")
    if clean_view == VIEW_DATE and on_date is None:
        raise HTTPException(status_code=400, detail="date is required when view is date")

    page_size = min(page_size, 100)
    today = today_ist()
    query = _apply_view(confirmed_query(db, current_user.society_id), clean_view, today, on_date)

    if search and search.strip():
        query = _search(query, search)

    order = (sort_order or "").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc" if clean_view == VIEW_HISTORY else "asc"

    sort_map = {
        "bookingDate": Booking.booking_date,
        "createdAt": Booking.created_at,
    }
    column = sort_map.get(sort_by, Booking.booking_date)
    direction = column.asc() if order == "asc" else column.desc()
    if column is Booking.booking_date:
        time_direction = Booking.start_time.asc() if order == "asc" else Booking.start_time.desc()
        query = query.order_by(direction, time_direction)
    else:
        query = query.order_by(direction)

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size)) if total else 1

    return BookingListData(
        items=[_to_item(*row) for row in rows],
        counts=_counts(db, current_user.society_id, today),
        pagination=Pagination(
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            hasNext=page < total_pages,
            hasPrev=page > 1,
        ),
    )


def get_booking(
    db: Session,
    current_user: GuardUser,
    booking_id: int,
) -> BookingItem:
    row = confirmed_query(db, current_user.society_id).filter(Booking.id == booking_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _to_item(*row)
