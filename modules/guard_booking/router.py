from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_booking.service import get_booking, list_bookings
from core.permissions import GATE_BOOKINGS_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response

router = APIRouter(tags=["Guard Bookings"])


@router.get("/guard/bookings")
def fetch_bookings(
    view: str = Query("today"),
    on_date: date | None = Query(None, alias="date"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("bookingDate"),
    sortOrder: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GATE_BOOKINGS_VIEW)),
):
    data = list_bookings(
        db,
        current_user,
        view=view,
        on_date=on_date,
        search=search,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Guard bookings fetched", data.model_dump(mode="json"))


@router.get("/guard/bookings/{booking_id}")
def fetch_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GATE_BOOKINGS_VIEW)),
):
    item = get_booking(db, current_user, booking_id)
    return success_response("Booking fetched", item.model_dump(mode="json"))
