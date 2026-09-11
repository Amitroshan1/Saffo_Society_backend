"""Amenities Booking System routes — admin/finance/guard/resident (Phase 13)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.facility_list_query import (
    get_facility_list_query,
    get_booking_list_query,
)
from Schemas.facility import (
    FacilityBookingSlotCreate,
    FacilityCreate,
    FacilityListQueryParams,
    FacilityUpdate,
    BookingApproveRequest,
    BookingListQueryParams,
    BookingRejectRequest,
    MaintenanceBlockCreate,
    RefundRequest,
)
from Services import facility_dashboard_service, facility_report_service, facility_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["facilities"])


# ---------------------------------------------------------------------------
# Admin — amenities
# ---------------------------------------------------------------------------


@router.post("/facilities")
async def create_facility(
    body: FacilityCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.create_facility(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Facility created successfully", data)


@router.get("/facilities")
async def list_facilities(
    query: FacilityListQueryParams = Depends(get_facility_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.list_facilities(db, query, actor_society_id=current.society_id)
    return success_response(200, "Facilities fetched", data)


@router.get("/facilities/dashboard")
async def amenities_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_dashboard_service.get_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Facilities dashboard fetched", data)


@router.get("/facilities/reports/{report_key}")
async def amenities_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    data = await facility_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={"from": from_date, "to": to_date},
    )
    return success_response(200, "Facilities report fetched", data)


@router.get("/facilities/{facility_id}")
async def get_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.get_facility(db, facility_id, actor_society_id=current.society_id)
    return success_response(200, "Facility fetched", data)


@router.patch("/facilities/{facility_id}")
async def update_facility(
    facility_id: UUID,
    body: FacilityUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.update_facility(
        db, facility_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Facility updated successfully", data)


@router.delete("/facilities/{facility_id}")
async def disable_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.disable_facility(
        db, facility_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Facility disabled", data)


@router.post("/facilities/{facility_id}/slots")
async def generate_amenity_slots(
    facility_id: UUID,
    body: FacilityBookingSlotCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.create_booking_slots(
        db, facility_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Facility slots generated", data)


@router.post("/facilities/{facility_id}/maintenance")
async def create_facility_maintenance_block(
    facility_id: UUID,
    body: MaintenanceBlockCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    if body.amenityId != facility_id:
        body = MaintenanceBlockCreate(
            amenityId=facility_id, startDate=body.startDate, endDate=body.endDate, reason=body.reason
        )
    data = await facility_service.create_maintenance_block(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Maintenance block created", data)


@router.get("/facilities/{facility_id}/maintenance")
async def list_facility_maintenance_blocks(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.list_maintenance_blocks(
        db, facility_id, actor_society_id=current.society_id
    )
    return success_response(200, "Maintenance blocks fetched", data)


@router.delete("/facilities/maintenance/{block_id}")
async def delete_facility_maintenance_block(
    block_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.delete_maintenance_block(
        db, block_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Maintenance block removed", data)


# ---------------------------------------------------------------------------
# Admin — bookings
# ---------------------------------------------------------------------------


@router.get("/bookings")
async def list_bookings(
    query: BookingListQueryParams = Depends(get_booking_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.list_bookings(db, query, actor_society_id=current.society_id)
    return success_response(200, "Bookings fetched", data)


@router.get("/bookings/{booking_id}")
async def get_booking(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.get_booking(db, booking_id, actor_society_id=current.society_id)
    return success_response(200, "Booking fetched", data)


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(
    booking_id: UUID,
    body: BookingApproveRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.approve_booking(
        db, booking_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking approved", data)


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(
    booking_id: UUID,
    body: BookingRejectRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await facility_service.reject_booking(
        db, booking_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Booking rejected", data)


# ---------------------------------------------------------------------------
# Finance portal
# ---------------------------------------------------------------------------


@router.get("/finance/facilities/revenue")
async def finance_amenity_revenue(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await facility_service.list_facility_revenue(
        db, actor_society_id=current.society_id, from_date=from_date, to_date=to_date
    )
    return success_response(200, "Facility revenue fetched", data)


@router.get("/finance/facilities/payments")
async def finance_amenity_payments(
    query: BookingListQueryParams = Depends(get_booking_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await facility_service.list_facility_payments(db, query, actor_society_id=current.society_id)
    return success_response(200, "Facility payments fetched", data)


@router.post("/finance/facilities/refund")
async def finance_process_refund(
    body: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await facility_service.process_refund(
        db,
        body.bookingId,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        reason=body.reason,
    )
    return success_response(200, "Refund processed", data)
