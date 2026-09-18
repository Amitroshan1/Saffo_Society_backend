"""Guard facility portal — bookings list, today's bookings, check-in, check-out."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.facility import Facility, FacilityBooking
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Schemas.facility import BookingCheckinRequest, BookingCheckoutRequest
from Schemas.guard_facility_schema import GuardBookingListQueryParams
from Schemas.common import build_pagination_meta
from Services import facility_service
from Services.facility_helpers import (
    booking_to_dict,
    get_booking_in_society,
    require_society_id,
)
from Utils.audit import apply_update_audit, utcnow
from Utils.errors import ApiError


async def _resident_flat_maps(
    db: AsyncSession, society_id: UUID, resident_ids: set[UUID]
) -> tuple[Dict[UUID, Resident], Dict[UUID, str]]:
    residents: Dict[UUID, Resident] = {}
    flat_by_resident: Dict[UUID, str] = {}
    if not resident_ids:
        return residents, flat_by_resident

    residents = {
        r.id: r
        for r in (
            await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
        ).scalars().all()
    }
    occ_rows = (
        await db.execute(
            select(Occupancy).where(
                Occupancy.resident_id.in_(resident_ids),
                Occupancy.society_id == society_id,
                Occupancy.status == "active",
            )
        )
    ).scalars().all()
    flat_ids = {o.flat_id for o in occ_rows}
    flats: Dict[UUID, Flat] = {}
    if flat_ids:
        flats = {
            f.id: f
            for f in (await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))).scalars().all()
        }
    for occ in occ_rows:
        flat = flats.get(occ.flat_id)
        if flat and occ.resident_id not in flat_by_resident:
            flat_by_resident[occ.resident_id] = flat.flat_no
    return residents, flat_by_resident


async def _serialize_guard_bookings(
    db: AsyncSession, society_id: UUID, rows: Sequence[FacilityBooking]
) -> List[Dict[str, Any]]:
    amenity_ids = {r.amenity_id for r in rows}
    amenities: Dict[UUID, Facility] = {}
    if amenity_ids:
        amenity_rows = (
            await db.execute(select(Facility).where(Facility.id.in_(amenity_ids)))
        ).scalars().all()
        amenities = {a.id: a for a in amenity_rows}

    residents, flat_by_resident = await _resident_flat_maps(
        db, society_id, {r.resident_id for r in rows}
    )

    bookings_out: List[Dict[str, Any]] = []
    for b in rows:
        data = booking_to_dict(b, amenity=amenities.get(b.amenity_id))
        resident = residents.get(b.resident_id)
        data["residentName"] = resident.name if resident else None
        data["flatNumber"] = flat_by_resident.get(b.resident_id)
        bookings_out.append(data)
    return bookings_out


def _apply_guard_booking_filters(base, query: GuardBookingListQueryParams, society_id: UUID):
    if query.status:
        base = base.where(FacilityBooking.status == query.status)
    if query.amenity_id:
        base = base.where(FacilityBooking.amenity_id == query.amenity_id)

    if query.booking_date:
        base = base.where(FacilityBooking.booking_date == query.booking_date)
    else:
        if query.from_date:
            base = base.where(FacilityBooking.booking_date >= query.from_date)
        if query.to_date:
            base = base.where(FacilityBooking.booking_date <= query.to_date)

    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        amenity_match = (
            select(Facility.id)
            .where(Facility.id == FacilityBooking.amenity_id, Facility.name.ilike(term))
            .exists()
        )
        resident_match = (
            select(Resident.id)
            .where(Resident.id == FacilityBooking.resident_id, Resident.name.ilike(term))
            .exists()
        )
        flat_match = (
            select(Occupancy.id)
            .join(Flat, Flat.id == Occupancy.flat_id)
            .where(
                Occupancy.resident_id == FacilityBooking.resident_id,
                Occupancy.society_id == society_id,
                Occupancy.status == "active",
                Flat.flat_no.ilike(term),
            )
            .exists()
        )
        base = base.where(
            or_(
                FacilityBooking.booking_code.ilike(term),
                FacilityBooking.booking_number.ilike(term),
                amenity_match,
                resident_match,
                flat_match,
            )
        )
    return base


async def list_bookings(
    db: AsyncSession, query: GuardBookingListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    """Guard booking history / upcoming / by-date list with filters, search, pagination."""
    society_id = require_society_id(actor_society_id)
    base = select(FacilityBooking).where(FacilityBooking.society_id == society_id)
    base = _apply_guard_booking_filters(base, query, society_id)

    allowed_sort = ("created_at", "updated_at", "booking_date", "status", "start_time")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "booking_date"
    sort_col = getattr(FacilityBooking, sort_field)
    ordered = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            ordered.offset((query.page - 1) * query.page_size).limit(query.page_size)
        )
    ).scalars().all()

    return {
        "bookings": await _serialize_guard_bookings(db, society_id, rows),
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def list_today_bookings(
    db: AsyncSession, query: GuardBookingListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today = date.today()
    base = select(FacilityBooking).where(
        FacilityBooking.society_id == society_id,
        FacilityBooking.booking_date == today,
        FacilityBooking.status.in_(("approved", "confirmed", "checked_in")),
    )
    if query.status:
        base = base.where(FacilityBooking.status == query.status)
    if query.amenity_id:
        base = base.where(FacilityBooking.amenity_id == query.amenity_id)

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(FacilityBooking.start_time.asc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()

    return {
        "bookings": await _serialize_guard_bookings(db, society_id, rows),
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def checkin_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingCheckinRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)

    if body.bookingCode and body.bookingCode != booking.booking_code:
        raise ApiError(422, "Booking code does not match")
    if booking.status not in ("approved", "confirmed"):
        raise ApiError(422, "Booking is not eligible for check-in")
    if booking.booking_date != date.today():
        raise ApiError(422, "Booking is not scheduled for today")

    now = utcnow()
    booking.status = "checked_in"
    booking.checked_in_at = now
    booking.checked_in_by = actor_id
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "BookingCheckedIn",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id)},
    )
    return await facility_service.get_booking(db, booking.id, actor_society_id=society_id)


async def checkout_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingCheckoutRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.status != "checked_in":
        raise ApiError(422, "Booking is not checked in")

    now = utcnow()
    booking.status = "completed"
    booking.checked_out_at = now
    booking.checked_out_by = actor_id
    booking.completed_at = now
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "BookingCheckedOut",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id)},
    )
    publish_simple(
        "BookingCompleted",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id)},
    )
    return await facility_service.get_booking(db, booking.id, actor_society_id=society_id)
