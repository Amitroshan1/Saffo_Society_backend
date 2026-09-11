"""Parking Management System routes — admin/finance/guard/resident (Phase 14)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.parking_list_query import (
    get_allocation_list_query,
    get_parking_slot_list_query,
    get_parking_zone_list_query,
    get_vehicle_list_query,
)
from Schemas.parking import (
    AllocationListQueryParams,
    ParkingAllocateRequest,
    ParkingRefundRequest,
    ParkingRevokeRequest,
    ParkingSlotCreate,
    ParkingSlotListQueryParams,
    ParkingSlotUpdate,
    ParkingTransferRequest,
    ParkingZoneCreate,
    ParkingZoneListQueryParams,
    ParkingZoneUpdate,
    VehicleListQueryParams,
)
from Services import parking_dashboard_service, parking_report_service, parking_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["parking"])


# ---------------------------------------------------------------------------
# Admin — zones
# ---------------------------------------------------------------------------


@router.post("/parking/zones")
async def create_zone(
    body: ParkingZoneCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.create_zone(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Parking zone created successfully", data)


@router.get("/parking/zones")
async def list_zones(
    query: ParkingZoneListQueryParams = Depends(get_parking_zone_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.list_zones(db, query, actor_society_id=current.society_id)
    return success_response(200, "Parking zones fetched", data)


@router.patch("/parking/zones/{zone_id}")
async def update_zone(
    zone_id: UUID,
    body: ParkingZoneUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.update_zone(
        db, zone_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking zone updated successfully", data)


@router.delete("/parking/zones/{zone_id}")
async def delete_zone(
    zone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.delete_zone(
        db, zone_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking zone disabled", data)


# ---------------------------------------------------------------------------
# Admin — slots
# ---------------------------------------------------------------------------


@router.post("/parking/slots")
async def create_slot(
    body: ParkingSlotCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.create_slot(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Parking slot created successfully", data)


@router.get("/parking/slots")
async def list_slots(
    query: ParkingSlotListQueryParams = Depends(get_parking_slot_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.list_slots(db, query, actor_society_id=current.society_id)
    return success_response(200, "Parking slots fetched", data)


@router.patch("/parking/slots/{slot_id}")
async def update_slot(
    slot_id: UUID,
    body: ParkingSlotUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.update_slot(
        db, slot_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking slot updated successfully", data)


# ---------------------------------------------------------------------------
# Admin — allocate / transfer / revoke
# ---------------------------------------------------------------------------


@router.post("/parking/allocate")
async def allocate_parking(
    body: ParkingAllocateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.allocate_slot(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Parking allocated successfully", data)


@router.post("/parking/transfer")
async def transfer_parking(
    body: ParkingTransferRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.transfer_allocation(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking transferred successfully", data)


@router.post("/parking/revoke")
async def revoke_parking(
    body: ParkingRevokeRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.revoke_allocation(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking allocation revoked", data)


@router.get("/parking/allocations")
async def list_allocations(
    query: AllocationListQueryParams = Depends(get_allocation_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.list_allocations(db, query, actor_society_id=current.society_id)
    return success_response(200, "Parking allocations fetched", data)


@router.get("/parking/vehicles")
async def list_vehicles(
    query: VehicleListQueryParams = Depends(get_vehicle_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_service.list_vehicles(db, query, actor_society_id=current.society_id)
    return success_response(200, "Vehicles fetched", data)


@router.get("/parking/dashboard")
async def parking_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await parking_dashboard_service.get_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Parking dashboard fetched", data)


@router.get("/parking/reports/{report_key}")
async def parking_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    year: str | None = Query(None),
):
    data = await parking_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={"from": from_date, "to": to_date, "year": year},
    )
    return success_response(200, "Parking report fetched", data)


# ---------------------------------------------------------------------------
# Finance portal
# ---------------------------------------------------------------------------


@router.get("/finance/parking/revenue")
async def finance_parking_revenue(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await parking_service.list_parking_revenue(
        db, actor_society_id=current.society_id, from_date=from_date, to_date=to_date
    )
    return success_response(200, "Parking revenue fetched", data)


@router.get("/finance/parking/payments")
async def finance_parking_payments(
    query: AllocationListQueryParams = Depends(get_allocation_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await parking_service.list_parking_payments(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Parking payments fetched", data)


@router.post("/finance/parking/refund")
async def finance_parking_refund(
    body: ParkingRefundRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await parking_service.process_refund(
        db,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        allocation_id=body.allocationId,
        visitor_log_id=body.visitorLogId,
        reason=body.reason,
    )
    return success_response(200, "Parking refund processed", data)
