"""Guard facility portal routes — /api/v1/guard/bookings/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.guard_facility_list_query import get_guard_booking_list_query
from Schemas.facility import BookingCheckinRequest, BookingCheckoutRequest
from Schemas.guard_facility_schema import GuardBookingListQueryParams
from Services import guard_facility_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-facilities"])


@router.get("/guard/bookings/today")
async def guard_today_bookings(
    query: GuardBookingListQueryParams = Depends(get_guard_booking_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_facility_service.list_today_bookings(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Today's bookings fetched", data)


@router.post("/guard/bookings/{booking_id}/checkin")
async def guard_checkin_booking(
    booking_id: UUID,
    body: BookingCheckinRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_facility_service.checkin_booking(
        db, booking_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking checked in", data)


@router.post("/guard/bookings/{booking_id}/checkout")
async def guard_checkout_booking(
    booking_id: UUID,
    body: BookingCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_facility_service.checkout_booking(
        db, booking_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking checked out", data)
