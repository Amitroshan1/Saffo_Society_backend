"""Resident facility portal — wraps shared facility service."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.facility import BookingCancelRequest, FacilityBookingCreate
from Schemas.resident_facility_schema import ResidentBookingListQueryParams
from Services import facility_service


async def list_available_facilities(
    db: AsyncSession, *, actor_society_id: UUID | None, query_date: Optional[date] = None
) -> Dict[str, Any]:
    return await facility_service.list_available_facilities(
        db, actor_society_id=actor_society_id, query_date=query_date
    )


async def get_facility_detail(
    db: AsyncSession, facility_id: UUID, *, actor_society_id: UUID | None, query_date: Optional[date] = None
) -> Dict[str, Any]:
    return await facility_service.get_facility_detail(
        db, facility_id, actor_society_id=actor_society_id, query_date=query_date
    )


async def create_booking(
    db: AsyncSession, body: FacilityBookingCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await facility_service.create_booking(
        db, body, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def list_my_bookings(
    db: AsyncSession,
    query: ResidentBookingListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await facility_service.list_my_bookings(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def get_my_booking(
    db: AsyncSession, booking_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await facility_service.get_my_booking(
        db, booking_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def cancel_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingCancelRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await facility_service.cancel_booking(
        db, booking_id, body, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def get_booking_receipt(
    db: AsyncSession, booking_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await facility_service.get_booking_receipt(
        db, booking_id, actor_id=actor_id, actor_society_id=actor_society_id
    )
