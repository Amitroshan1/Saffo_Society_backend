"""Guard facility portal — today's bookings, check-in, check-out."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.facility import Facility, FacilityBooking, FacilityCheckin
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

    amenity_ids = {r.amenity_id for r in rows}
    amenities = {}
    if amenity_ids:
        amenity_rows = (
            await db.execute(select(Facility).where(Facility.id.in_(amenity_ids)))
        ).scalars().all()
        amenities = {a.id: a for a in amenity_rows}

    resident_ids = {r.resident_id for r in rows}
    residents: Dict[UUID, Resident] = {}
    flat_by_resident: Dict[UUID, str] = {}
    if resident_ids:
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
        flats = {}
        if flat_ids:
            flats = {
                f.id: f
                for f in (
                    await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
                ).scalars().all()
            }
        for occ in occ_rows:
            flat = flats.get(occ.flat_id)
            if flat and occ.resident_id not in flat_by_resident:
                flat_by_resident[occ.resident_id] = flat.flat_no

    bookings_out = []
    for b in rows:
        data = booking_to_dict(b, amenity=amenities.get(b.amenity_id))
        resident = residents.get(b.resident_id)
        data["residentName"] = resident.name if resident else None
        data["flatNumber"] = flat_by_resident.get(b.resident_id)
        bookings_out.append(data)

    return {
        "bookings": bookings_out,
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
    db.add(
        FacilityCheckin(
            booking_id=booking.id,
            society_id=society_id,
            action="check_in",
            performed_by=actor_id,
            performed_at=now,
            notes=body.notes,
            metadata_json={},
        )
    )
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
    db.add(
        FacilityCheckin(
            booking_id=booking.id,
            society_id=society_id,
            action="check_out",
            performed_by=actor_id,
            performed_at=now,
            notes=body.notes,
            metadata_json={},
        )
    )
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
