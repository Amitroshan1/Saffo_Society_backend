"""Platform dashboard, analytics rollups, health, jobs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from Models.facility import FacilityBooking
from Models.complaint import Complaint
from Models.parking import ParkingSlot
from Models.platform import (
    License,
    PlatformJobRun,
    PlatformMetricDaily,
    Tenant,
    TenantSubscription,
    SubscriptionPlan,
)
from Models.resident import Resident
from Models.user import User
from Models.visit import Visit
from Services.platform_helpers import finish_job, iso, start_job, utcnow
from Services.platform_settings_service import get_maintenance

_dashboard_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


async def get_platform_dashboard(db: AsyncSession) -> Dict[str, Any]:
    import time

    now = time.time()
    if _dashboard_cache["data"] and now - _dashboard_cache["ts"] < 60:
        return dict(_dashboard_cache["data"])

    total = int((await db.execute(select(func.count()).select_from(Tenant))).scalar() or 0)
    active = int(
        (
            await db.execute(
                select(func.count()).select_from(Tenant).where(Tenant.status == "active")
            )
        ).scalar()
        or 0
    )
    inactive = total - active

    users = int((await db.execute(select(func.count()).select_from(User))).scalar() or 0)
    residents = int(
        (await db.execute(select(func.count()).select_from(Resident))).scalar() or 0
    )
    complaints = int(
        (await db.execute(select(func.count()).select_from(Complaint))).scalar() or 0
    )
    visitors = int((await db.execute(select(func.count()).select_from(Visit))).scalar() or 0)
    parking = int(
        (await db.execute(select(func.count()).select_from(ParkingSlot))).scalar() or 0
    )
    bookings = int(
        (await db.execute(select(func.count()).select_from(FacilityBooking))).scalar() or 0
    )

    # Platform subscription revenue (active/trialing plans price sum — approximate MRR snapshot)
    rev_q = await db.execute(
        select(func.coalesce(func.sum(SubscriptionPlan.price_minor), 0))
        .select_from(TenantSubscription)
        .join(SubscriptionPlan, SubscriptionPlan.id == TenantSubscription.plan_id)
        .where(
            TenantSubscription.is_active.is_(True),
            TenantSubscription.status.in_(("active", "trialing", "grace")),
        )
    )
    revenue_minor = int(rev_q.scalar() or 0)

    maintenance = await get_maintenance(db)
    health = await get_platform_health(db)

    recent_jobs = (
        await db.execute(
            select(PlatformJobRun).order_by(PlatformJobRun.created_at.desc()).limit(5)
        )
    ).scalars().all()

    data = {
        "kpis": {
            "totalTenants": total,
            "activeTenants": active,
            "inactiveTenants": inactive,
            "residents": residents,
            "users": users,
            "subscriptionRevenueMinor": revenue_minor,
            "storageUsageGb": 0,
            "apiRequests": 0,
            "complaints": complaints,
            "visitors": visitors,
            "parkingSlots": parking,
            "bookings": bookings,
            "workerStatus": "ok" if health.get("status") != "down" else "degraded",
            "platformHealth": health.get("status"),
        },
        "maintenance": maintenance,
        "recentJobs": [
            {
                "id": str(j.id),
                "jobKey": j.job_key,
                "status": j.status,
                "createdAt": iso(j.created_at),
            }
            for j in recent_jobs
        ],
        "asOf": iso(utcnow()),
        "sourceFreshness": "live",
    }
    _dashboard_cache["ts"] = now
    _dashboard_cache["data"] = data
    return data


async def get_platform_analytics(db: AsyncSession, key: str) -> Dict[str, Any]:
    today = date.today()
    if key == "tenant.growth":
        rows = (
            await db.execute(
                select(func.date(Tenant.created_at), func.count())
                .group_by(func.date(Tenant.created_at))
                .order_by(func.date(Tenant.created_at))
            )
        ).all()
        return {
            "key": key,
            "series": [{"date": str(d), "count": int(c)} for d, c in rows if d],
            "asOf": iso(utcnow()),
        }
    if key == "subscription.trends":
        rows = (
            await db.execute(
                select(TenantSubscription.status, func.count()).group_by(TenantSubscription.status)
            )
        ).all()
        return {
            "key": key,
            "distribution": {str(s): int(c) for s, c in rows},
            "asOf": iso(utcnow()),
        }
    if key == "license.distribution":
        rows = (
            await db.execute(select(License.status, func.count()).group_by(License.status))
        ).all()
        return {
            "key": key,
            "distribution": {str(s): int(c) for s, c in rows},
            "asOf": iso(utcnow()),
        }
    if key == "feature.adoption":
        from Services.platform_feature_service import list_flags
        from Models.platform import TenantFeatureFlag

        flags = await list_flags(db)
        overrides = (
            await db.execute(
                select(TenantFeatureFlag.flag_key, TenantFeatureFlag.mode, func.count())
                .group_by(TenantFeatureFlag.flag_key, TenantFeatureFlag.mode)
            )
        ).all()
        return {
            "key": key,
            "flags": flags,
            "overrides": [
                {"key": k, "mode": m, "count": int(c)} for k, m, c in overrides
            ],
            "asOf": iso(utcnow()),
        }
    if key in ("storage.usage", "api.usage", "worker.queue", "system.errors", "active.users"):
        # Prefer rolled-up metrics when present
        metric_rows = (
            await db.execute(
                select(PlatformMetricDaily)
                .where(
                    PlatformMetricDaily.metric_key == key,
                    PlatformMetricDaily.metric_date >= today - timedelta(days=30),
                )
                .order_by(PlatformMetricDaily.metric_date)
            )
        ).scalars().all()
        return {
            "key": key,
            "series": [
                {
                    "date": str(r.metric_date),
                    "value": float(r.value_num),
                    "valueInt": int(r.value_int),
                }
                for r in metric_rows
            ],
            "note": "Populate via metric rollup job; empty until rolled up.",
            "asOf": iso(utcnow()),
        }
    return {"key": key, "message": "Unknown analytics key", "asOf": iso(utcnow())}


async def rollup_platform_metrics(db: AsyncSession) -> Dict[str, Any]:
    job = await start_job(db, "platform.metric_rollup")
    today = date.today()
    total_tenants = int((await db.execute(select(func.count()).select_from(Tenant))).scalar() or 0)
    active_users = int(
        (
            await db.execute(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
        ).scalar()
        or 0
    )
    metrics = {
        "tenant.growth": total_tenants,
        "active.users": active_users,
        "api.usage": 0,
        "storage.usage": 0,
        "worker.queue": 0,
        "system.errors": 0,
    }
    for key, val in metrics.items():
        existing = (
            await db.execute(
                select(PlatformMetricDaily).where(
                    PlatformMetricDaily.metric_date == today,
                    PlatformMetricDaily.metric_key == key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.value_int = val
            existing.value_num = val
        else:
            db.add(
                PlatformMetricDaily(
                    id=uuid4(),
                    metric_date=today,
                    metric_key=key,
                    value_int=val,
                    value_num=val,
                )
            )
    await finish_job(db, job, status="succeeded", result=metrics)
    await db.commit()
    _dashboard_cache["data"] = None
    return {"date": str(today), "metrics": metrics}


async def get_platform_health(db: AsyncSession) -> Dict[str, Any]:
    components: List[dict] = []

    # API self
    components.append({"name": "api", "status": "healthy"})

    # Database
    try:
        await db.execute(text("SELECT 1"))
        components.append({"name": "database", "status": "healthy"})
    except Exception as exc:
        components.append({"name": "database", "status": "down", "detail": str(exc)[:200]})

    # Redis / cache — optional
    try:
        from Core.config import settings

        redis_url = getattr(settings, "REDIS_URL", None) or ""
        if redis_url:
            components.append({"name": "redis", "status": "configured"})
        else:
            components.append({"name": "redis", "status": "not_configured"})
    except Exception:
        components.append({"name": "redis", "status": "not_configured"})

    for name in ("queue", "object_storage", "smtp", "sms", "push"):
        components.append({"name": name, "status": "not_configured"})

    # Workers — last job heartbeat
    last_job = (
        await db.execute(
            select(PlatformJobRun).order_by(PlatformJobRun.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    components.append(
        {
            "name": "workers",
            "status": "healthy" if last_job else "idle",
            "lastJob": last_job.job_key if last_job else None,
        }
    )

    # Migrations — best effort
    try:
        rev = (
            await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        ).scalar()
        components.append(
            {
                "name": "migrations",
                "status": "healthy",
                "head": str(rev) if rev else None,
            }
        )
    except Exception:
        components.append({"name": "migrations", "status": "unknown"})

    statuses = {c["status"] for c in components}
    if "down" in statuses:
        overall = "down"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return {"status": overall, "components": components, "asOf": iso(utcnow())}


async def list_job_runs(db: AsyncSession, limit: int = 50) -> List[dict]:
    rows = (
        await db.execute(
            select(PlatformJobRun).order_by(PlatformJobRun.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "jobKey": r.job_key,
            "status": r.status,
            "startedAt": iso(r.started_at),
            "finishedAt": iso(r.finished_at),
            "durationMs": r.duration_ms,
            "errorMessage": r.error_message,
            "result": r.result_json or {},
            "createdAt": iso(r.created_at),
        }
        for r in rows
    ]


async def list_audit_logs(
    db: AsyncSession, *, page: int = 1, page_size: int = 50, action: str | None = None
) -> Dict[str, Any]:
    from Models.platform import PlatformAuditLog
    from Schemas.common import build_pagination_meta

    stmt = select(PlatformAuditLog)
    count_stmt = select(func.count()).select_from(PlatformAuditLog)
    if action:
        stmt = stmt.where(PlatformAuditLog.action == action)
        count_stmt = count_stmt.where(PlatformAuditLog.action == action)
    total = int((await db.execute(count_stmt)).scalar() or 0)
    rows = (
        await db.execute(
            stmt.order_by(PlatformAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "actorUserId": str(r.actor_user_id) if r.actor_user_id else None,
                "actorRole": r.actor_role,
                "action": r.action,
                "resourceType": r.resource_type,
                "resourceId": r.resource_id,
                "tenantId": str(r.tenant_id) if r.tenant_id else None,
                "before": r.before_json,
                "after": r.after_json,
                "createdAt": iso(r.created_at),
            }
            for r in rows
        ],
        "pagination": build_pagination_meta(page, page_size, total),
    }
