"""Resident facility portal routes — /api/v1/resident/facilities|bookings."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.resident_facility_list_query import get_resident_booking_list_query
from Schemas.facility import BookingCancelRequest, FacilityBookingCreate
from Schemas.resident_facility_schema import ResidentBookingListQueryParams
from Services import resident_facility_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-facilities"])


@router.get("/resident/facilities")
async def resident_list_facilities(
    on_date: date | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.list_available_facilities(
        db, actor_society_id=current.society_id, query_date=on_date
    )
    return success_response(200, "Available amenities fetched", data)


@router.get("/resident/facilities/{facility_id}")
async def resident_get_facility(
    facility_id: UUID,
    on_date: date | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.get_facility_detail(
        db, facility_id, actor_society_id=current.society_id, query_date=on_date
    )
    return success_response(200, "Facility detail fetched", data)


@router.post("/resident/bookings")
async def resident_create_booking(
    body: FacilityBookingCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.create_booking(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Booking created successfully", data)


@router.get("/resident/bookings")
async def resident_list_bookings(
    query: ResidentBookingListQueryParams = Depends(get_resident_booking_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.list_my_bookings(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "My bookings fetched", data)


@router.get("/resident/bookings/{booking_id}")
async def resident_get_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.get_my_booking(
        db, booking_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking fetched", data)


@router.post("/resident/bookings/{booking_id}/cancel")
async def resident_cancel_booking(
    booking_id: UUID,
    body: BookingCancelRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.cancel_booking(
        db, booking_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking cancelled", data)


@router.get("/resident/bookings/{booking_id}/receipt")
async def resident_booking_receipt(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_facility_service.get_booking_receipt(
        db, booking_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking receipt fetched", data)
