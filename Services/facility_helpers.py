"""Facility helpers — lookups, numbering, validation, serialization."""

from __future__ import annotations

import random
import string
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.facility import (
    Facility,
    FacilityBooking,
    FacilityMaintenanceBlock,
)
from Utils.audit import utcnow
from Utils.errors import ApiError

ACTIVE_BOOKING_STATUSES = ("pending", "approved", "confirmed", "checked_in")
TERMINAL_BOOKING_STATUSES = ("rejected", "cancelled", "expired")


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def get_facility_in_society(db: AsyncSession, facility_id: UUID, society_id: UUID) -> Facility:
    result = await db.execute(
        select(Facility).where(Facility.id == facility_id, Facility.society_id == society_id)
    )
    facility = result.scalar_one_or_none()
    if not facility:
        raise ApiError(404, "Facility not found")
    return facility


async def get_booking_in_society(
    db: AsyncSession, booking_id: UUID, society_id: UUID
) -> FacilityBooking:
    result = await db.execute(
        select(FacilityBooking).where(
            FacilityBooking.id == booking_id, FacilityBooking.society_id == society_id
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise ApiError(404, "Booking not found")
    return booking


async def next_booking_number(db: AsyncSession, society_id: UUID) -> str:
    count = (
        await db.execute(
            select(func.count()).where(FacilityBooking.society_id == society_id)
        )
    ).scalar_one()
    return f"BKG-{int(count) + 1:06d}"


def generate_booking_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=6))


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "amenity"


def combine_dt(d: date, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=timezone.utc)


def time_to_minutes(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(value: int) -> str:
    h, m = divmod(value, 60)
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Availability & limits
# ---------------------------------------------------------------------------


async def check_slot_availability(
    db: AsyncSession,
    amenity: Facility,
    *,
    booking_date: date,
    start_time: str,
    end_time: str,
    exclude_booking_id: Optional[UUID] = None,
) -> None:
    today = date.today()
    if booking_date < today:
        raise ApiError(422, "Booking date cannot be in the past")

    max_date = today + timedelta(days=amenity.advance_booking_days or 30)
    if booking_date > max_date:
        raise ApiError(
            422, f"Bookings can only be made up to {amenity.advance_booking_days} days in advance"
        )

    if amenity.available_days:
        weekday = str(booking_date.weekday())
        if weekday not in amenity.available_days:
            raise ApiError(422, "Facility is not available on the selected day")

    if amenity.operating_hours_start and start_time < amenity.operating_hours_start:
        raise ApiError(422, "Booking start time is before amenity operating hours")
    if amenity.operating_hours_end and end_time > amenity.operating_hours_end:
        raise ApiError(422, "Booking end time is after amenity operating hours")

    maintenance = (
        await db.execute(
            select(FacilityMaintenanceBlock).where(
                FacilityMaintenanceBlock.amenity_id == amenity.id,
                FacilityMaintenanceBlock.is_active.is_(True),
                FacilityMaintenanceBlock.start_date <= booking_date,
                FacilityMaintenanceBlock.end_date >= booking_date,
            )
        )
    ).scalar_one_or_none()
    if maintenance:
        raise ApiError(422, "Facility is under maintenance on the selected date")

    overlap_stmt = select(FacilityBooking).where(
        FacilityBooking.amenity_id == amenity.id,
        FacilityBooking.booking_date == booking_date,
        FacilityBooking.status.in_(ACTIVE_BOOKING_STATUSES),
        FacilityBooking.start_time < end_time,
        FacilityBooking.end_time > start_time,
    )
    if exclude_booking_id:
        overlap_stmt = overlap_stmt.where(FacilityBooking.id != exclude_booking_id)
    overlapping = (await db.execute(overlap_stmt)).scalars().all()
    if len(overlapping) >= amenity.capacity:
        raise ApiError(409, "Facility is fully booked for the selected time slot")


async def check_resident_booking_limit(
    db: AsyncSession,
    amenity: Facility,
    *,
    resident_id: UUID,
    booking_date: date,
    exclude_booking_id: Optional[UUID] = None,
) -> None:
    if not amenity.max_bookings_per_resident:
        return
    stmt = select(func.count()).where(
        FacilityBooking.amenity_id == amenity.id,
        FacilityBooking.resident_id == resident_id,
        FacilityBooking.booking_date == booking_date,
        FacilityBooking.status.in_(ACTIVE_BOOKING_STATUSES),
    )
    if exclude_booking_id:
        stmt = stmt.where(FacilityBooking.id != exclude_booking_id)
    count = int((await db.execute(stmt)).scalar_one())
    if count >= amenity.max_bookings_per_resident:
        raise ApiError(
            422,
            f"Maximum {amenity.max_bookings_per_resident} booking(s) per day allowed for this amenity",
        )


def generate_time_windows(amenity: Facility, query_date: date) -> list[tuple[str, str]]:
    """Build bookable [start, end] windows from amenity hours — not stored rows."""
    if amenity.available_days:
        weekday = str(query_date.weekday())
        if weekday not in amenity.available_days:
            return []
    if not amenity.operating_hours_start or not amenity.operating_hours_end:
        return []
    start_minutes = time_to_minutes(amenity.operating_hours_start)
    end_minutes = time_to_minutes(amenity.operating_hours_end)
    duration = amenity.slot_duration_minutes or 0
    if duration <= 0 or start_minutes >= end_minutes:
        return []
    windows: list[tuple[str, str]] = []
    t = start_minutes
    while t + duration <= end_minutes:
        windows.append((minutes_to_time(t), minutes_to_time(t + duration)))
        t += duration
    return windows


def count_overlapping_bookings(bookings: list[FacilityBooking], start_time: str, end_time: str) -> int:
    return sum(1 for b in bookings if b.start_time < end_time and b.end_time > start_time)


def generated_slot_to_dict(
    amenity: Facility,
    *,
    query_date: date,
    start_time: str,
    end_time: str,
    booked_count: int,
    is_blocked: bool = False,
    block_reason: Optional[str] = None,
) -> Dict[str, Any]:
    capacity = amenity.capacity or 0
    remaining = 0 if is_blocked else max(0, capacity - booked_count)
    return {
        "id": None,
        "amenityId": str(amenity.id),
        "societyId": str(amenity.society_id),
        "date": query_date.isoformat(),
        "startTime": start_time,
        "endTime": end_time,
        "capacity": capacity,
        "bookedCount": booked_count,
        "isBlocked": is_blocked,
        "blockReason": block_reason,
        "available": remaining,
    }


def is_within_cancellation_window(booking: FacilityBooking, amenity: Facility) -> bool:
    booking_start = combine_dt(booking.booking_date, booking.start_time)
    cutoff = booking_start - timedelta(hours=amenity.cancellation_hours or 0)
    return utcnow() <= cutoff


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def facility_to_dict(amenity: Facility) -> Dict[str, Any]:
    return {
        "id": str(amenity.id),
        "societyId": str(amenity.society_id),
        "name": amenity.name,
        "slug": amenity.slug,
        "description": amenity.description,
        "category": amenity.category,
        "location": amenity.location,
        "capacity": amenity.capacity,
        "isPaid": amenity.is_paid,
        "pricePerSlot": amenity.price_per_slot,
        "securityDeposit": amenity.security_deposit,
        "slotDurationMinutes": amenity.slot_duration_minutes,
        "advanceBookingDays": amenity.advance_booking_days,
        "cancellationHours": amenity.cancellation_hours,
        "maxBookingsPerResident": amenity.max_bookings_per_resident,
        "requiresApproval": amenity.requires_approval,
        "operatingHoursStart": amenity.operating_hours_start,
        "operatingHoursEnd": amenity.operating_hours_end,
        "availableDays": amenity.available_days,
        "rulesText": amenity.rules_text,
        "imageUrl": amenity.image_url,
        "status": amenity.status,
        "metadata": amenity.metadata_json or {},
        "notes": amenity.notes,
        "isActive": amenity.is_active,
        "version": amenity.version,
        "createdAt": amenity.created_at.isoformat() if amenity.created_at else None,
        "updatedAt": amenity.updated_at.isoformat() if amenity.updated_at else None,
    }


def booking_to_dict(booking: FacilityBooking, *, amenity: Optional[Facility] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": str(booking.id),
        "societyId": str(booking.society_id),
        "amenityId": str(booking.amenity_id),
        "amenityName": amenity.name if amenity else None,
        "slotId": None,
        "residentId": str(booking.resident_id),
        "userId": str(booking.user_id),
        "bookingNumber": booking.booking_number,
        "bookingDate": booking.booking_date.isoformat() if booking.booking_date else None,
        "startTime": booking.start_time,
        "endTime": booking.end_time,
        "guestCount": booking.guest_count,
        "purpose": booking.purpose,
        "status": booking.status,
        "amount": booking.amount,
        "securityDeposit": booking.security_deposit,
        "paymentStatus": booking.payment_status,
        "paymentReference": booking.payment_reference,
        "approvedBy": str(booking.approved_by) if booking.approved_by else None,
        "approvedAt": booking.approved_at.isoformat() if booking.approved_at else None,
        "rejectedReason": booking.rejected_reason,
        "cancelledAt": booking.cancelled_at.isoformat() if booking.cancelled_at else None,
        "cancellationReason": booking.cancellation_reason,
        "checkedInAt": booking.checked_in_at.isoformat() if booking.checked_in_at else None,
        "checkedInBy": str(booking.checked_in_by) if booking.checked_in_by else None,
        "checkedOutAt": booking.checked_out_at.isoformat() if booking.checked_out_at else None,
        "checkedOutBy": str(booking.checked_out_by) if booking.checked_out_by else None,
        "completedAt": booking.completed_at.isoformat() if booking.completed_at else None,
        "bookingCode": booking.booking_code,
        "metadata": booking.metadata_json or {},
        "notes": booking.notes,
        "isActive": booking.is_active,
        "version": booking.version,
        "createdAt": booking.created_at.isoformat() if booking.created_at else None,
        "updatedAt": booking.updated_at.isoformat() if booking.updated_at else None,
    }
    return data


def maintenance_block_to_dict(block: FacilityMaintenanceBlock) -> Dict[str, Any]:
    return {
        "id": str(block.id),
        "amenityId": str(block.amenity_id),
        "societyId": str(block.society_id),
        "startDate": block.start_date.isoformat() if block.start_date else None,
        "endDate": block.end_date.isoformat() if block.end_date else None,
        "reason": block.reason,
        "createdBy": str(block.created_by) if block.created_by else None,
        "isActive": block.is_active,
        "createdAt": block.created_at.isoformat() if block.created_at else None,
    }
