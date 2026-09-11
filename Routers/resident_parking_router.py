"""Resident parking portal routes — /api/v1/resident/parking/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.parking_list_query import get_allocation_list_query, get_vehicle_list_query
from Schemas.parking import (
    AllocationListQueryParams,
    VehicleCreate,
    VehicleListQueryParams,
    VehicleUpdate,
    VisitorParkingCreate,
)
from Services import resident_parking_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-parking"])


@router.get("/resident/parking")
async def resident_parking(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_parking_overview(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident parking fetched", data)


@router.post("/resident/vehicles")
async def resident_create_vehicle(
    body: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_create_vehicle(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Vehicle registered successfully", data)


@router.get("/resident/vehicles")
async def resident_list_vehicles(
    query: VehicleListQueryParams = Depends(get_vehicle_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_list_vehicles(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "My vehicles fetched", data)


@router.patch("/resident/vehicles/{vehicle_id}")
async def resident_update_vehicle(
    vehicle_id: UUID,
    body: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_update_vehicle(
        db, vehicle_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Vehicle updated successfully", data)


@router.post("/resident/visitor-parking")
async def resident_visitor_parking(
    body: VisitorParkingCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_create_visitor_parking(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Visitor parking request created", data)


@router.get("/resident/parking/history")
async def resident_parking_history(
    query: AllocationListQueryParams = Depends(get_allocation_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_parking_history(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking history fetched", data)


@router.get("/resident/parking/receipt/{allocation_id}")
async def resident_parking_receipt(
    allocation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_parking_service.resident_parking_receipt(
        db, allocation_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Parking receipt fetched", data)
