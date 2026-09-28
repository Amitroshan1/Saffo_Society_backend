from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from modules.facility.models import Amenity, Booking
from modules.facility.schemas import BookingCreate, CancelIn
from modules.resident.service import _occupancy_or_404


def _minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _out(row: Booking) -> dict:
    return {
        "id": row.id,
        "amenity_id": row.amenity_id,
        "amenity_name": row.amenity.name,
        "booking_date": row.booking_date,
        "start_time": row.start_time,
        "end_time": row.end_time,
        "guest_count": row.guest_count,
        "purpose": row.purpose,
        "status": row.status,
        "cancel_reason": row.cancel_reason,
    }


def list_facilities(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(Amenity)
        .filter(Amenity.society_id == occupancy.society_id, Amenity.is_bookable == True)
        .order_by(Amenity.name.asc())
        .all()
    )
    return [
        {"id": a.id, "name": a.name, "open_time": a.open_time, "close_time": a.close_time}
        for a in rows
    ]


def slots_for_day(db: Session, user_id: int, society_id: int | None, amenity_id: int, day: date) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    amenity = (
        db.query(Amenity)
        .filter(Amenity.id == amenity_id, Amenity.society_id == occupancy.society_id)
        .first()
    )
    if not amenity:
        raise HTTPException(status_code=404, detail="Facility not found")
    booked = (
        db.query(Booking)
        .filter(
            Booking.amenity_id == amenity.id,
            Booking.booking_date == day,
            Booking.status == "booked",
        )
        .all()
    )
    taken = {(b.start_time, b.end_time) for b in booked}
    start = _minutes(amenity.open_time)
    end = _minutes(amenity.close_time)
    slots = []
    while start + 60 <= end:
        label_start = _label(start)
        label_end = _label(start + 60)
        slots.append(
            {
                "start_time": label_start,
                "end_time": label_end,
                "is_booked": (label_start, label_end) in taken,
            }
        )
        start += 60
    return slots


def create_booking(db: Session, user_id: int, society_id: int | None, data: BookingCreate) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    amenity = (
        db.query(Amenity)
        .filter(
            Amenity.id == data.amenity_id,
            Amenity.society_id == occupancy.society_id,
            Amenity.is_bookable == True,
        )
        .first()
    )
    if not amenity:
        raise HTTPException(status_code=404, detail="Facility not found")
    if _minutes(data.start_time) >= _minutes(data.end_time):
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    clash = (
        db.query(Booking)
        .filter(
            Booking.amenity_id == amenity.id,
            Booking.booking_date == data.booking_date,
            Booking.status == "booked",
            Booking.start_time < data.end_time,
            Booking.end_time > data.start_time,
        )
        .first()
    )
    if clash:
        raise HTTPException(status_code=409, detail="Slot already booked")
    row = Booking(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        amenity_id=amenity.id,
        booking_date=data.booking_date,
        start_time=data.start_time,
        end_time=data.end_time,
        guest_count=data.guest_count,
        purpose=data.purpose,
        status="booked",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.amenity = amenity
    return _out(row)


def list_bookings(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(Booking)
        .options(joinedload(Booking.amenity))
        .filter(Booking.occupancy_id == occupancy.id, Booking.society_id == occupancy.society_id)
        .order_by(Booking.id.desc())
        .all()
    )
    return [_out(r) for r in rows]


def get_booking(db: Session, user_id: int, society_id: int | None, booking_id: int) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    row = (
        db.query(Booking)
        .options(joinedload(Booking.amenity))
        .filter(
            Booking.id == booking_id,
            Booking.occupancy_id == occupancy.id,
            Booking.society_id == occupancy.society_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _out(row)


def cancel_booking(
    db: Session, user_id: int, society_id: int | None, booking_id: int, data: CancelIn
) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    row = (
        db.query(Booking)
        .options(joinedload(Booking.amenity))
        .filter(
            Booking.id == booking_id,
            Booking.occupancy_id == occupancy.id,
            Booking.society_id == occupancy.society_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    if row.status == "cancelled":
        raise HTTPException(status_code=400, detail="Booking already cancelled")
    row.status = "cancelled"
    row.cancel_reason = data.reason
    db.commit()
    db.refresh(row)
    return _out(row)