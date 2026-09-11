"""Guard dashboard portal routes — /api/v1/guard/dashboard, sos, deliveries, activity."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Services import guard_dashboard_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-dashboard"])


@router.get("/guard/dashboard/stats")
async def guard_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.get_dashboard_stats(
        db, actor_society_id=current.society_id
    )
    return success_response(200, "Guard dashboard stats fetched", data)


@router.get("/guard/sos")
async def guard_sos_alerts(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.list_sos_alerts(
        db, actor_society_id=current.society_id
    )
    return success_response(200, "SOS alerts fetched", data)


@router.patch("/guard/sos/{sos_id}/respond")
async def guard_sos_respond(
    sos_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.respond_to_sos(
        db,
        sos_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "SOS marked as responded", data)


@router.get("/guard/deliveries")
async def guard_pending_deliveries(
    collected: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.list_pending_deliveries(
        db,
        actor_society_id=current.society_id,
        collected=collected,
        limit=limit,
    )
    return success_response(200, "Guard deliveries fetched", data)


@router.patch("/guard/deliveries/{delivery_id}/collect")
async def guard_collect_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.collect_delivery(
        db,
        delivery_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Delivery marked collected", data)


@router.get("/guard/staff-inside")
async def guard_staff_inside(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.list_staff_inside(
        db, actor_society_id=current.society_id, limit=limit
    )
    return success_response(200, "Staff inside fetched", data)


@router.get("/guard/activity")
async def guard_recent_activity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_dashboard_service.list_recent_activity(
        db, actor_society_id=current.society_id, limit=limit
    )
    return success_response(200, "Recent activity fetched", data)
