"""Analytics API routes (Phase 16)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Schemas.analytics import (
    ExportCreateRequest,
    PreferencesUpdateRequest,
    RebuildRequest,
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
)
from Services import analytics_service as svc
from Services.analytics_helpers import require_society_id
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["analytics"])

ADMIN_ROLES = ("admin",)
FINANCE_ROLES = ("admin", "finance")
ANY_ANALYTICS = ("admin", "finance", "guard", "resident")


async def _resident_id(db: AsyncSession, user_id: UUID) -> UUID | None:
    from sqlalchemy import select
    from Models.resident import Resident

    row = (
        await db.execute(select(Resident.id).where(Resident.user_id == user_id, Resident.is_active.is_(True)))
    ).scalar_one_or_none()
    return row


@router.get("/analytics/catalog")
async def catalog(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.get_catalog(db, society_id, current.role)
    await db.commit()
    return success_response(200, "Analytics catalog fetched", data)


@router.get("/analytics/dashboards/{key}")
async def dashboard(
    key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    rid = await _resident_id(db, current.user_id) if current.role == "resident" else None
    data = await svc.get_dashboard(
        db,
        society_id,
        current.role,
        layout_key=key if key not in ("me", "default") else None,
        user_id=current.user_id,
        resident_id=rid,
    )
    # if key is role-specific alias
    if key in ("executive", "finance", "today", "summary"):
        data = await svc.get_dashboard(
            db, society_id, current.role, key, user_id=current.user_id, resident_id=rid
        )
    await db.commit()
    return success_response(200, "Dashboard fetched", data)


@router.get("/analytics/kpis")
async def kpis(
    keys: str | None = Query(None),
    live: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    key_list = [k.strip() for k in keys.split(",")] if keys else None
    data = await svc.get_kpis(db, society_id, current.role, key_list, live=live)
    await db.commit()
    return success_response(200, "KPIs fetched", {"kpis": data})


@router.get("/analytics/kpis/{kpi_key}")
async def kpi_one(
    kpi_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.get_kpis(db, society_id, current.role, [kpi_key], live=True)
    if not data:
        from Utils.errors import ApiError

        raise ApiError(404, "KPI not found")
    await db.commit()
    return success_response(200, "KPI fetched", data[0])


@router.get("/analytics/charts/{chart_key}")
async def charts(
    chart_key: str,
    chartType: str = Query("bar"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.chart_series(db, society_id, current.role, chart_key, chartType)
    await db.commit()
    return success_response(200, "Chart fetched", data)


@router.get("/analytics/reports")
async def reports_list(
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.list_reports(db, society_id, current.role, category, search)
    await db.commit()
    return success_response(200, "Reports listed", {"reports": data})


@router.get("/analytics/reports/{report_key}")
async def report_run(
    report_key: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    rid = await _resident_id(db, current.user_id) if current.role == "resident" else None
    data = await svc.execute_report(
        db,
        society_id,
        current.role,
        report_key,
        page=page,
        page_size=pageSize,
        user_id=current.user_id,
        resident_id=rid,
    )
    await db.commit()
    return success_response(200, "Report executed", data)


@router.post("/analytics/rebuild")
async def rebuild(
    body: RebuildRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    society_id = require_society_id(current.society_id)
    from_d = date.fromisoformat(body.fromDate) if body.fromDate else None
    to_d = date.fromisoformat(body.toDate) if body.toDate else None
    data = await svc.rebuild_range(db, society_id, from_d, to_d)
    await db.commit()
    return success_response(200, "Analytics rebuild completed", data)


@router.post("/analytics/snapshots/refresh")
async def snapshots_refresh(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.refresh_kpi_snapshots(db, society_id, current.user_id)
    await db.commit()
    return success_response(200, "KPI snapshots refreshed", data)


@router.post("/analytics/exports")
async def exports_create(
    body: ExportCreateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    rid = await _resident_id(db, current.user_id) if current.role == "resident" else None
    data = await svc.create_export(
        db,
        society_id,
        current.role,
        report_key=body.reportKey,
        format=body.format,
        filters=body.filters,
        user_id=current.user_id,
        resident_id=rid,
    )
    await db.commit()
    return success_response(201, "Export created", data)


@router.get("/analytics/exports")
async def exports_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.list_exports(db, society_id, current.user_id, current.role, page, pageSize)
    await db.commit()
    return success_response(200, "Exports listed", data)


@router.get("/analytics/exports/{export_id}")
async def exports_get(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    job = await svc.get_export(db, society_id, export_id, current.user_id, current.role)
    await db.commit()
    return success_response(200, "Export fetched", svc.serialize_export(job))


@router.get("/analytics/exports/{export_id}/download")
async def exports_download(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    job, content = await svc.download_export(
        db, society_id, export_id, current.user_id, current.role
    )
    await db.commit()
    media = "text/csv" if job.format in ("csv", "excel") else "text/plain"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{job.file_name or "export.csv"}"'},
    )


@router.post("/analytics/schedules")
async def schedules_create(
    body: ScheduleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.create_schedule(
        db, society_id, current.user_id, body.model_dump(), current.role
    )
    await db.commit()
    return success_response(201, "Schedule created", data)


@router.get("/analytics/schedules")
async def schedules_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.list_schedules(db, society_id, current.role, page, pageSize)
    await db.commit()
    return success_response(200, "Schedules listed", data)


@router.patch("/analytics/schedules/{schedule_id}")
async def schedules_update(
    schedule_id: UUID,
    body: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.update_schedule(
        db, society_id, schedule_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return success_response(200, "Schedule updated", data)


@router.delete("/analytics/schedules/{schedule_id}")
async def schedules_delete(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    await svc.soft_delete_schedule(db, society_id, schedule_id)
    await db.commit()
    return success_response(200, "Schedule disabled", {})


@router.get("/analytics/schedules/{schedule_id}/runs")
async def schedules_runs(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.list_schedule_runs(db, society_id, schedule_id)
    await db.commit()
    return success_response(200, "Schedule runs listed", {"runs": data})


@router.get("/analytics/preferences")
async def prefs_get(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.get_preferences(db, society_id, current.user_id)
    await db.commit()
    return success_response(200, "Preferences fetched", data)


@router.patch("/analytics/preferences")
async def prefs_patch(
    body: PreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ANY_ANALYTICS)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.patch_preferences(
        db, society_id, current.user_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return success_response(200, "Preferences updated", data)


@router.get("/analytics/access-logs")
async def access_logs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.list_access_logs(db, society_id, page, pageSize)
    await db.commit()
    return success_response(200, "Access logs fetched", data)


@router.get("/finance/analytics/dashboard")
async def finance_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.get_dashboard(
        db, society_id, "finance", "finance", user_id=current.user_id
    )
    await db.commit()
    return success_response(200, "Finance analytics dashboard fetched", data)
