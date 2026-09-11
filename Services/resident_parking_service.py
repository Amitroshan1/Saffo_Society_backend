"""Resident parking portal — wraps shared parking service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.parking import (
    AllocationListQueryParams,
    VehicleCreate,
    VehicleListQueryParams,
    VehicleUpdate,
    VisitorParkingCreate,
)
from Services import parking_service


async def resident_parking_overview(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_parking_overview(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_list_vehicles(
    db: AsyncSession, query: VehicleListQueryParams, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_list_vehicles(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_create_vehicle(
    db: AsyncSession, body: VehicleCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_create_vehicle(
        db, body, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_update_vehicle(
    db: AsyncSession,
    vehicle_id: UUID,
    body: VehicleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await parking_service.resident_update_vehicle(
        db, vehicle_id, body, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_create_visitor_parking(
    db: AsyncSession, body: VisitorParkingCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_create_visitor_parking(
        db, body, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_parking_history(
    db: AsyncSession, query: AllocationListQueryParams, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_parking_history(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_parking_receipt(
    db: AsyncSession, allocation_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await parking_service.resident_parking_receipt(
        db, allocation_id, actor_id=actor_id, actor_society_id=actor_society_id
    )
