from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_resident
from modules.facility import service
from modules.facility.schemas import AmenityOut, BookingCreate, BookingOut, CancelIn, SlotOut

router = APIRouter(prefix="/resident", tags=["Resident facilities"])


@router.get("/facilities", response_model=list[AmenityOut])
def facilities(
    date: date | None = Query(None),
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.list_facilities(db, ctx.user.id, ctx.society_id)


@router.get("/facilities/{amenity_id}", response_model=list[SlotOut])
def facility_slots(
    amenity_id: int,
    day: date = Query(...),
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.slots_for_day(db, ctx.user.id, ctx.society_id, amenity_id, day)


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(
    data: BookingCreate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.create_booking(db, ctx.user.id, ctx.society_id, data)


@router.get("/bookings", response_model=list[BookingOut])
def bookings(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_bookings(db, ctx.user.id, ctx.society_id)


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def booking_detail(
    booking_id: int,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.get_booking(db, ctx.user.id, ctx.society_id, booking_id)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    data: CancelIn,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.cancel_booking(db, ctx.user.id, ctx.society_id, booking_id, data)