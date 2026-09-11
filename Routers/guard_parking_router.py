"""Guard parking portal routes — /api/v1/guard/parking/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.parking_list_query import get_visitor_parking_list_query
from Schemas.parking import (
    ParkingEntryRequest,
    ParkingExitRequest,
    VisitorParkingCreate,
    VisitorParkingListQueryParams,
)
from Services import guard_parking_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-parking"])


@router.get("/guard/parking/today")
async def guard_parking_today(
    query: VisitorParkingListQueryParams = Depends(get_visitor_parking_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_parking_service.guard_today(db, query, actor_society_id=current.society_id)
    return success_response(200, "Today's parking status fetched", data)


@router.post("/guard/parking/entry")
async def guard_parking_entry(
    body: ParkingEntryRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_parking_service.vehicle_entry(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Vehicle entry recorded", data)


@router.post("/guard/parking/exit")
async def guard_parking_exit(
    body: ParkingExitRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_parking_service.vehicle_exit(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Vehicle exit recorded", data)


@router.post("/guard/visitor-parking")
async def guard_visitor_parking(
    body: VisitorParkingCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_parking_service.create_visitor_parking(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Visitor parking created", data)
