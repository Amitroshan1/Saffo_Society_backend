"""Facility business logic — CRUD, slots, bookings, guard/finance/resident flows (Phase 13)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.facility import (
    Facility,
    FacilityBooking,
    FacilityMaintenanceBlock,
)
from Models.resident import Resident
from Schemas.facility import (
    FacilityBookingCreate,
    FacilityBookingSlotCreate,
    FacilityCreate,
    FacilityListQueryParams,
    FacilityUpdate,
    BookingApproveRequest,
    BookingCancelRequest,
    BookingListQueryParams,
    BookingRejectRequest,
    MaintenanceBlockCreate,
    ResidentBookingListQueryParams,
)
from Schemas.common import build_pagination_meta
from Services.facility_helpers import (
    ACTIVE_BOOKING_STATUSES,
    facility_to_dict,
    booking_to_dict,
    check_resident_booking_limit,
    check_slot_availability,
    count_overlapping_bookings,
    generate_booking_code,
    generate_time_windows,
    generated_slot_to_dict,
    get_facility_in_society,
    get_booking_in_society,
    is_within_cancellation_window,
    maintenance_block_to_dict,
    next_booking_number,
    require_society_id,
    slugify,
    time_to_minutes,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

FACILITY_FIELD_MAP = {
    "name": "name",
    "description": "description",
    "category": "category",
    "location": "location",
    "capacity": "capacity",
    "isPaid": "is_paid",
    "pricePerSlot": "price_per_slot",
    "securityDeposit": "security_deposit",
    "slotDurationMinutes": "slot_duration_minutes",
    "advanceBookingDays": "advance_booking_days",
    "cancellationHours": "cancellation_hours",
    "maxBookingsPerResident": "max_bookings_per_resident",
    "requiresApproval": "requires_approval",
    "operatingHoursStart": "operating_hours_start",
    "operatingHoursEnd": "operating_hours_end",
    "availableDays": "available_days",
    "rulesText": "rules_text",
    "imageUrl": "image_url",
    "status": "status",
    "notes": "notes",
    "metadata": "metadata_json",
}


async def _resolve_resident(db: AsyncSession, *, actor_id: UUID, society_id: UUID) -> Resident:
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")
    return resident


async def _unique_slug(db: AsyncSession, society_id: UUID, name: str) -> str:
    base = slugify(name)
    slug = base
    suffix = 1
    while True:
        existing = (
            await db.execute(
                select(Facility.id).where(Facility.society_id == society_id, Facility.slug == slug)
            )
        ).scalar_one_or_none()
        if not existing:
            return slug
        suffix += 1
        slug = f"{base}-{suffix}"


# ---------------------------------------------------------------------------
# Admin — amenities
# ---------------------------------------------------------------------------


async def create_facility(
    db: AsyncSession, body: FacilityCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    slug = await _unique_slug(db, society_id, body.name)

    amenity = Facility(
        society_id=society_id,
        name=body.name,
        slug=slug,
        description=body.description,
        category=body.category,
        location=body.location,
        capacity=body.capacity,
        is_paid=body.isPaid,
        price_per_slot=body.pricePerSlot,
        security_deposit=body.securityDeposit,
        slot_duration_minutes=body.slotDurationMinutes,
        advance_booking_days=body.advanceBookingDays,
        cancellation_hours=body.cancellationHours,
        max_bookings_per_resident=body.maxBookingsPerResident,
        requires_approval=body.requiresApproval,
        operating_hours_start=body.operatingHoursStart,
        operating_hours_end=body.operatingHoursEnd,
        available_days=body.availableDays,
        rules_text=body.rulesText,
        image_url=body.imageUrl,
        status="active",
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(amenity, actor_id)
    db.add(amenity)
    await db.commit()
    await db.refresh(amenity)

    publish_simple(
        "FacilityCreated",
        society_id=society_id,
        entity_type="amenity",
        entity_id=amenity.id,
        actor_id=actor_id,
        payload={"amenityId": str(amenity.id), "name": amenity.name},
    )
    return {"facility": facility_to_dict(amenity)}


async def list_facilities(
    db: AsyncSession, query: FacilityListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(Facility).where(Facility.society_id == society_id)

    if query.status:
        base = base.where(Facility.status == query.status)
    if query.category:
        base = base.where(Facility.category == query.category)
    if query.is_paid is not None:
        base = base.where(Facility.is_paid == query.is_paid)
    if query.is_active is not None:
        base = base.where(Facility.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(or_(Facility.name.ilike(term), Facility.description.ilike(term)))

    allowed_sort = ("created_at", "updated_at", "name", "category", "status", "capacity")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Facility, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()

    return {
        "facilities": [facility_to_dict(a) for a in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_facility(
    db: AsyncSession, facility_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)
    return {"facility": facility_to_dict(amenity)}


async def update_facility(
    db: AsyncSession,
    facility_id: UUID,
    body: FacilityUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)

    data = body.model_dump(exclude_unset=True)
    changed_fields = []
    for api_key, orm_key in FACILITY_FIELD_MAP.items():
        if api_key in data:
            setattr(amenity, orm_key, data[api_key])
            changed_fields.append(api_key)

    apply_update_audit(amenity, actor_id)
    await db.commit()
    await db.refresh(amenity)

    if changed_fields:
        publish_simple(
            "FacilityUpdated",
            society_id=society_id,
            entity_type="amenity",
            entity_id=amenity.id,
            actor_id=actor_id,
            payload={"amenityId": str(amenity.id), "changedFields": changed_fields},
        )
    return {"facility": facility_to_dict(amenity)}


async def disable_facility(
    db: AsyncSession, facility_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)
    amenity.is_active = False
    amenity.status = "inactive"
    apply_update_audit(amenity, actor_id)
    await db.commit()

    publish_simple(
        "FacilityDisabled",
        society_id=society_id,
        entity_type="amenity",
        entity_id=amenity.id,
        actor_id=actor_id,
        payload={"amenityId": str(amenity.id)},
    )
    return {"amenityId": str(amenity.id), "isActive": False, "status": amenity.status}


# ---------------------------------------------------------------------------
# Admin — slots & maintenance
# ---------------------------------------------------------------------------


async def create_booking_slots(
    db: AsyncSession,
    facility_id: UUID,
    body: FacilityBookingSlotCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    """Kept for the admin Generate slots UI. Windows are derived from amenity hours, not stored."""
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)
    if not amenity.operating_hours_start or not amenity.operating_hours_end:
        raise ApiError(422, "Configure amenity operating hours before generating slots")

    start_minutes = time_to_minutes(amenity.operating_hours_start)
    end_minutes = time_to_minutes(amenity.operating_hours_end)
    duration = amenity.slot_duration_minutes
    if duration <= 0 or start_minutes >= end_minutes:
        raise ApiError(422, "Facility operating hours/slot duration are misconfigured")

    created = 0
    current_date = body.startDate
    while current_date <= body.endDate:
        created += len(generate_time_windows(amenity, current_date))
        current_date += timedelta(days=1)

    return {
        "amenityId": str(amenity.id),
        "startDate": body.startDate.isoformat(),
        "endDate": body.endDate.isoformat(),
        "slotsCreated": created,
    }


async def create_maintenance_block(
    db: AsyncSession, body: MaintenanceBlockCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, body.amenityId, society_id)

    block = FacilityMaintenanceBlock(
        amenity_id=amenity.id,
        society_id=society_id,
        start_date=body.startDate,
        end_date=body.endDate,
        reason=body.reason,
        created_by=actor_id,
        metadata_json={},
        is_active=True,
    )
    db.add(block)
    await db.commit()
    await db.refresh(block)

    publish_simple(
        "MaintenanceScheduled",
        society_id=society_id,
        entity_type="amenity",
        entity_id=amenity.id,
        actor_id=actor_id,
        payload={"amenityId": str(amenity.id), "blockId": str(block.id)},
    )
    return {"maintenanceBlock": maintenance_block_to_dict(block)}


async def list_maintenance_blocks(
    db: AsyncSession, facility_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)
    rows = (
        await db.execute(
            select(FacilityMaintenanceBlock)
            .where(FacilityMaintenanceBlock.amenity_id == amenity.id)
            .order_by(FacilityMaintenanceBlock.start_date.desc())
        )
    ).scalars().all()
    return {"maintenanceBlocks": [maintenance_block_to_dict(b) for b in rows]}


async def delete_maintenance_block(
    db: AsyncSession, block_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    block = (
        await db.execute(
            select(FacilityMaintenanceBlock).where(
                FacilityMaintenanceBlock.id == block_id,
                FacilityMaintenanceBlock.society_id == society_id,
            )
        )
    ).scalar_one_or_none()
    if not block:
        raise ApiError(404, "Maintenance block not found")
    block.is_active = False
    await db.commit()
    return {"maintenanceBlockId": str(block.id), "isActive": False}


# ---------------------------------------------------------------------------
# Admin — bookings
# ---------------------------------------------------------------------------


async def list_bookings(
    db: AsyncSession, query: BookingListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(FacilityBooking).where(FacilityBooking.society_id == society_id)

    if query.status:
        base = base.where(FacilityBooking.status == query.status)
    if query.amenity_id:
        base = base.where(FacilityBooking.amenity_id == query.amenity_id)
    if query.from_date:
        base = base.where(FacilityBooking.booking_date >= query.from_date)
    if query.to_date:
        base = base.where(FacilityBooking.booking_date <= query.to_date)
    if query.is_active is not None:
        base = base.where(FacilityBooking.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(FacilityBooking.booking_number.ilike(term), FacilityBooking.booking_code.ilike(term))
        )

    allowed_sort = ("created_at", "updated_at", "booking_date", "status", "amount")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(FacilityBooking, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()

    amenity_ids = {r.amenity_id for r in rows}
    amenities = {}
    if amenity_ids:
        amenity_rows = (
            await db.execute(select(Facility).where(Facility.id.in_(amenity_ids)))
        ).scalars().all()
        amenities = {a.id: a for a in amenity_rows}

    return {
        "bookings": [booking_to_dict(b, amenity=amenities.get(b.amenity_id)) for b in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_booking(
    db: AsyncSession, booking_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    amenity = await get_facility_in_society(db, booking.amenity_id, society_id)
    return {"booking": booking_to_dict(booking, amenity=amenity)}


async def approve_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingApproveRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.status != "pending":
        raise ApiError(422, "Only pending bookings can be approved")

    booking.status = "approved"
    booking.approved_by = actor_id
    booking.approved_at = utcnow()
    if body.notes:
        booking.notes = body.notes
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "BookingApproved",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id), "bookingNumber": booking.booking_number},
    )
    return await get_booking(db, booking.id, actor_society_id=society_id)


async def reject_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingRejectRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.status != "pending":
        raise ApiError(422, "Only pending bookings can be rejected")

    booking.status = "rejected"
    booking.rejected_reason = body.reason
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "BookingRejected",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id), "reason": body.reason},
    )
    return await get_booking(db, booking.id, actor_society_id=society_id)


# ---------------------------------------------------------------------------
# Resident portal
# ---------------------------------------------------------------------------


async def list_available_facilities(
    db: AsyncSession, *, actor_society_id: UUID | None, query_date: Optional[date] = None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    rows = (
        await db.execute(
            select(Facility)
            .where(Facility.society_id == society_id, Facility.status == "active", Facility.is_active.is_(True))
            .order_by(Facility.name.asc())
        )
    ).scalars().all()

    result = []
    for amenity in rows:
        data = facility_to_dict(amenity)
        if query_date:
            booked = int(
                (
                    await db.execute(
                        select(func.count()).where(
                            FacilityBooking.amenity_id == amenity.id,
                            FacilityBooking.booking_date == query_date,
                            FacilityBooking.status.in_(ACTIVE_BOOKING_STATUSES),
                        )
                    )
                ).scalar_one()
            )
            data["bookedCount"] = booked
            data["hasAvailability"] = booked < amenity.capacity
        result.append(data)
    return {"facilities": result}


async def get_facility_detail(
    db: AsyncSession, facility_id: UUID, *, actor_society_id: UUID | None, query_date: Optional[date] = None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    amenity = await get_facility_in_society(db, facility_id, society_id)
    if amenity.status != "active" or not amenity.is_active:
        raise ApiError(404, "Facility not found")

    data = facility_to_dict(amenity)
    if query_date:
        maintenance = (
            await db.execute(
                select(FacilityMaintenanceBlock).where(
                    FacilityMaintenanceBlock.amenity_id == amenity.id,
                    FacilityMaintenanceBlock.is_active.is_(True),
                    FacilityMaintenanceBlock.start_date <= query_date,
                    FacilityMaintenanceBlock.end_date >= query_date,
                )
            )
        ).scalar_one_or_none()
        bookings = (
            await db.execute(
                select(FacilityBooking).where(
                    FacilityBooking.amenity_id == amenity.id,
                    FacilityBooking.booking_date == query_date,
                    FacilityBooking.status.in_(ACTIVE_BOOKING_STATUSES),
                )
            )
        ).scalars().all()
        is_blocked = bool(maintenance)
        block_reason = maintenance.reason if maintenance else None
        data["slots"] = [
            generated_slot_to_dict(
                amenity,
                query_date=query_date,
                start_time=start_time,
                end_time=end_time,
                booked_count=count_overlapping_bookings(bookings, start_time, end_time),
                is_blocked=is_blocked,
                block_reason=block_reason,
            )
            for start_time, end_time in generate_time_windows(amenity, query_date)
        ]
        data["isUnderMaintenance"] = is_blocked
    return {"facility": data}


async def create_booking(
    db: AsyncSession, body: FacilityBookingCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    amenity = await get_facility_in_society(db, body.amenityId, society_id)
    if amenity.status != "active" or not amenity.is_active:
        raise ApiError(422, "Facility is not available for booking")

    await check_slot_availability(
        db, amenity, booking_date=body.bookingDate, start_time=body.startTime, end_time=body.endTime
    )
    await check_resident_booking_limit(
        db, amenity, resident_id=resident.id, booking_date=body.bookingDate
    )

    amount = amenity.price_per_slot if amenity.is_paid else 0
    status = "pending" if amenity.requires_approval else "confirmed"
    payment_status = "pending" if (amenity.is_paid and amount) else "not_required"

    booking_number = await next_booking_number(db, society_id)
    booking_code = generate_booking_code()
    for _ in range(5):
        exists = (
            await db.execute(select(FacilityBooking.id).where(FacilityBooking.booking_code == booking_code))
        ).scalar_one_or_none()
        if not exists:
            break
        booking_code = generate_booking_code()

    booking = FacilityBooking(
        society_id=society_id,
        amenity_id=amenity.id,
        resident_id=resident.id,
        user_id=actor_id,
        booking_number=booking_number,
        booking_date=body.bookingDate,
        start_time=body.startTime,
        end_time=body.endTime,
        guest_count=body.guestCount,
        purpose=body.purpose,
        status=status,
        amount=amount or 0,
        security_deposit=amenity.security_deposit or 0,
        payment_status=payment_status,
        booking_code=booking_code,
        metadata_json={},
        is_active=True,
        version=1,
    )
    apply_create_audit(booking, actor_id)
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    publish_simple(
        "BookingCreated",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id), "amenityId": str(amenity.id), "status": booking.status},
    )
    return {"booking": booking_to_dict(booking, amenity=amenity)}


async def list_my_bookings(
    db: AsyncSession,
    query: ResidentBookingListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)

    base = select(FacilityBooking).where(
        FacilityBooking.society_id == society_id, FacilityBooking.resident_id == resident.id
    )
    if query.status:
        base = base.where(FacilityBooking.status == query.status)

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(FacilityBooking.created_at.desc())
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

    return {
        "bookings": [booking_to_dict(b, amenity=amenities.get(b.amenity_id)) for b in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_my_booking(
    db: AsyncSession, booking_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.resident_id != resident.id:
        raise ApiError(404, "Booking not found")
    amenity = await get_facility_in_society(db, booking.amenity_id, society_id)
    return {"booking": booking_to_dict(booking, amenity=amenity)}


async def cancel_booking(
    db: AsyncSession,
    booking_id: UUID,
    body: BookingCancelRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.resident_id != resident.id:
        raise ApiError(404, "Booking not found")
    if booking.status not in ("pending", "approved", "confirmed"):
        raise ApiError(422, "Booking cannot be cancelled from its current status")

    amenity = await get_facility_in_society(db, booking.amenity_id, society_id)
    if not is_within_cancellation_window(booking, amenity):
        raise ApiError(
            422, f"Cancellation window has passed ({amenity.cancellation_hours}h before booking start)"
        )

    booking.status = "cancelled"
    booking.cancelled_at = utcnow()
    booking.cancellation_reason = body.reason
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "BookingCancelled",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id), "reason": body.reason},
    )
    return await get_my_booking(db, booking.id, actor_id=actor_id, actor_society_id=society_id)


async def get_booking_receipt(
    db: AsyncSession, booking_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident = await _resolve_resident(db, actor_id=actor_id, society_id=society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.resident_id != resident.id:
        raise ApiError(404, "Booking not found")
    amenity = await get_facility_in_society(db, booking.amenity_id, society_id)

    return {
        "receipt": {
            "bookingId": str(booking.id),
            "bookingNumber": booking.booking_number,
            "bookingCode": booking.booking_code,
            "amenityName": amenity.name,
            "residentName": resident.name,
            "bookingDate": booking.booking_date.isoformat(),
            "startTime": booking.start_time,
            "endTime": booking.end_time,
            "guestCount": booking.guest_count,
            "status": booking.status,
            "amount": booking.amount,
            "securityDeposit": booking.security_deposit,
            "paymentStatus": booking.payment_status,
            "issuedAt": utcnow().isoformat(),
        }
    }


# ---------------------------------------------------------------------------
# Finance portal
# ---------------------------------------------------------------------------


async def list_facility_revenue(
    db: AsyncSession, *, actor_society_id: UUID | None, from_date: Optional[date], to_date: Optional[date]
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    stmt = (
        select(
            Facility.id,
            Facility.name,
            func.count(FacilityBooking.id),
            func.coalesce(func.sum(FacilityBooking.amount), 0),
        )
        .join(FacilityBooking, FacilityBooking.amenity_id == Facility.id)
        .where(
            Facility.society_id == society_id,
            FacilityBooking.payment_status == "paid",
            FacilityBooking.status.notin_(("cancelled", "rejected")),
        )
    )
    if from_date:
        stmt = stmt.where(FacilityBooking.booking_date >= from_date)
    if to_date:
        stmt = stmt.where(FacilityBooking.booking_date <= to_date)
    stmt = stmt.group_by(Facility.id, Facility.name)

    rows = (await db.execute(stmt)).all()
    revenue = [
        {"amenityId": str(aid), "amenityName": name, "bookingCount": int(cnt), "totalRevenue": int(total)}
        for aid, name, cnt, total in rows
    ]
    total_revenue = sum(r["totalRevenue"] for r in revenue)
    return {"revenue": revenue, "totalRevenue": total_revenue}


async def list_facility_payments(
    db: AsyncSession, query: BookingListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(FacilityBooking).where(
        FacilityBooking.society_id == society_id, FacilityBooking.amount > 0
    )
    if query.status:
        base = base.where(FacilityBooking.status == query.status)
    if query.amenity_id:
        base = base.where(FacilityBooking.amenity_id == query.amenity_id)
    if query.from_date:
        base = base.where(FacilityBooking.booking_date >= query.from_date)
    if query.to_date:
        base = base.where(FacilityBooking.booking_date <= query.to_date)

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(FacilityBooking.created_at.desc())
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

    return {
        "payments": [booking_to_dict(b, amenity=amenities.get(b.amenity_id)) for b in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def process_refund(
    db: AsyncSession,
    booking_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    booking = await get_booking_in_society(db, booking_id, society_id)
    if booking.payment_status not in ("paid", "partially_refunded"):
        raise ApiError(422, "Booking has no payment eligible for refund")

    booking.payment_status = "refunded"
    apply_update_audit(booking, actor_id)
    await db.commit()

    publish_simple(
        "RefundProcessed",
        society_id=society_id,
        entity_type="amenity_booking",
        entity_id=booking.id,
        actor_id=actor_id,
        payload={"bookingId": str(booking.id), "reason": reason},
    )
    return {"bookingId": str(booking.id), "paymentStatus": booking.payment_status}
