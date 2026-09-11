"""Subscription plans & tenant subscriptions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.platform import SubscriptionPlan, Tenant, TenantSubscription
from Services.platform_helpers import (
    DEFAULT_PLANS,
    emit_platform_event,
    plan_to_dict,
    subscription_to_dict,
    utcnow,
    write_audit,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError


async def ensure_default_plans(db: AsyncSession, actor_id: UUID | None = None) -> None:
    existing = {
        p.code
        for p in (await db.execute(select(SubscriptionPlan))).scalars().all()
    }
    for d in DEFAULT_PLANS:
        if d["code"] in existing:
            continue
        row = SubscriptionPlan(
            code=d["code"],
            name=d["name"],
            billing_period=d["billing_period"],
            price_minor=d["price_minor"],
            trial_days=d.get("trial_days", 0),
            limits_json=d.get("limits_json") or {},
            features_json=d.get("features_json") or {},
            is_public=d.get("is_public", True),
            sort_order=d.get("sort_order", 0),
            description=d.get("description"),
        )
        if actor_id:
            apply_create_audit(row, actor_id)
        db.add(row)
    await db.flush()


async def list_plans(db: AsyncSession) -> List[dict]:
    await ensure_default_plans(db)
    rows = (
        await db.execute(
            select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order, SubscriptionPlan.code)
        )
    ).scalars().all()
    return [plan_to_dict(r) for r in rows]


async def upsert_plan(
    db: AsyncSession,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    code = body["code"].strip().lower()
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code))
    row = result.scalar_one_or_none()
    if not row:
        row = SubscriptionPlan(
            code=code,
            name=body.get("name") or code,
            billing_period=body.get("billingPeriod") or "monthly",
        )
        apply_create_audit(row, actor_id)
        db.add(row)
    else:
        apply_update_audit(row, actor_id)
    for field, attr in (
        ("name", "name"),
        ("description", "description"),
        ("billingPeriod", "billing_period"),
        ("priceMinor", "price_minor"),
        ("currency", "currency"),
        ("trialDays", "trial_days"),
        ("isPublic", "is_public"),
        ("sortOrder", "sort_order"),
    ):
        if field in body and body[field] is not None:
            setattr(row, attr, body[field])
    if "limits" in body and body["limits"] is not None:
        row.limits_json = body["limits"]
    if "features" in body and body["features"] is not None:
        row.features_json = body["features"]
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="plan.upsert",
        resource_type="subscription_plan",
        resource_id=str(row.id),
        after=plan_to_dict(row),
    )
    await db.commit()
    await db.refresh(row)
    return plan_to_dict(row)


async def get_plan_by_code(db: AsyncSession, code: str) -> SubscriptionPlan:
    await ensure_default_plans(db)
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == code.lower())
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise ApiError(404, "Plan not found")
    return plan


def _period_delta(period: str, trial_days: int = 0) -> timedelta:
    if period == "trial":
        return timedelta(days=trial_days or 14)
    if period == "yearly":
        return timedelta(days=365)
    if period == "enterprise":
        return timedelta(days=365)
    return timedelta(days=30)


async def ensure_subscription_for_tenant(
    db: AsyncSession,
    tenant: Tenant,
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    existing = await get_active_subscription(db, tenant.id)
    if existing:
        return existing
    plan_code = (tenant.plan_code or "trial").lower()
    plan = await get_plan_by_code(db, plan_code)
    now = utcnow()
    ends = now + _period_delta(plan.billing_period, plan.trial_days)
    status = "trialing" if plan.billing_period == "trial" or plan.trial_days else "active"
    sub = TenantSubscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=status,
        billing_period=plan.billing_period,
        starts_at=now,
        ends_at=ends,
        trial_ends_at=now + timedelta(days=plan.trial_days) if plan.trial_days else None,
        auto_renew=True,
    )
    apply_create_audit(sub, actor_id)
    db.add(sub)
    await db.flush()
    tenant.plan_code = plan.code
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="subscription.create",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        tenant_id=tenant.id,
        after=subscription_to_dict(sub),
    )
    emit_platform_event(
        "SubscriptionCreated",
        tenant_id=tenant.id,
        entity_type="tenant_subscription",
        entity_id=sub.id,
        actor_id=actor_id,
    )
    return subscription_to_dict(sub)


async def get_active_subscription(
    db: AsyncSession, tenant_id: UUID
) -> Optional[dict]:
    result = await db.execute(
        select(TenantSubscription)
        .where(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.is_active.is_(True),
        )
        .order_by(TenantSubscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return None
    data = subscription_to_dict(sub)
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
    ).scalar_one_or_none()
    if plan:
        data["plan"] = plan_to_dict(plan)
    return data


async def list_subscriptions(
    db: AsyncSession, *, tenant_id: UUID | None = None
) -> List[dict]:
    stmt = select(TenantSubscription).order_by(TenantSubscription.created_at.desc())
    if tenant_id:
        stmt = stmt.where(TenantSubscription.tenant_id == tenant_id)
    rows = (await db.execute(stmt.limit(200))).scalars().all()
    return [subscription_to_dict(r) for r in rows]


async def assign_plan(
    db: AsyncSession,
    tenant_id: UUID,
    plan_code: str,
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    from Services.platform_tenant_service import resolve_tenant

    tenant = await resolve_tenant(db, tenant_id)
    plan = await get_plan_by_code(db, plan_code)
    # deactivate previous
    prev = (
        await db.execute(
            select(TenantSubscription).where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.is_active.is_(True),
            )
        )
    ).scalars().all()
    for p in prev:
        p.is_active = False
        if p.status not in ("cancelled", "expired"):
            p.status = "cancelled"
            p.cancelled_at = utcnow()
        apply_update_audit(p, actor_id)

    now = utcnow()
    ends = now + _period_delta(plan.billing_period, plan.trial_days)
    status = "trialing" if plan.billing_period == "trial" else "active"
    sub = TenantSubscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=status,
        billing_period=plan.billing_period,
        starts_at=now,
        ends_at=ends,
        trial_ends_at=now + timedelta(days=plan.trial_days) if plan.trial_days else None,
        auto_renew=True,
    )
    apply_create_audit(sub, actor_id)
    db.add(sub)
    tenant.plan_code = plan.code
    apply_update_audit(tenant, actor_id)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="subscription.assign",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        tenant_id=tenant.id,
        after=subscription_to_dict(sub),
    )
    emit_platform_event(
        "SubscriptionCreated",
        tenant_id=tenant.id,
        entity_type="tenant_subscription",
        entity_id=sub.id,
        actor_id=actor_id,
        payload={"planCode": plan.code},
    )
    await db.commit()
    return await get_active_subscription(db, tenant_id) or {}


async def renew_subscription(
    db: AsyncSession, subscription_id: UUID, *, actor_id: UUID, actor_role: str
) -> dict:
    result = await db.execute(
        select(TenantSubscription).where(TenantSubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise ApiError(404, "Subscription not found")
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
    ).scalar_one()
    base = sub.ends_at or utcnow()
    if base < utcnow():
        base = utcnow()
    sub.ends_at = base + _period_delta(plan.billing_period, plan.trial_days)
    sub.status = "active"
    sub.grace_ends_at = None
    apply_update_audit(sub, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="subscription.renew",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        tenant_id=sub.tenant_id,
        after=subscription_to_dict(sub),
    )
    emit_platform_event(
        "SubscriptionRenewed",
        tenant_id=sub.tenant_id,
        entity_type="tenant_subscription",
        entity_id=sub.id,
        actor_id=actor_id,
    )
    await db.commit()
    return subscription_to_dict(sub)


async def cancel_subscription(
    db: AsyncSession, subscription_id: UUID, *, actor_id: UUID, actor_role: str
) -> dict:
    result = await db.execute(
        select(TenantSubscription).where(TenantSubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise ApiError(404, "Subscription not found")
    sub.status = "cancelled"
    sub.cancelled_at = utcnow()
    sub.auto_renew = False
    apply_update_audit(sub, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="subscription.cancel",
        resource_type="tenant_subscription",
        resource_id=str(sub.id),
        tenant_id=sub.tenant_id,
        after=subscription_to_dict(sub),
    )
    emit_platform_event(
        "SubscriptionCancelled",
        tenant_id=sub.tenant_id,
        entity_type="tenant_subscription",
        entity_id=sub.id,
        actor_id=actor_id,
    )
    await db.commit()
    return subscription_to_dict(sub)


async def get_effective_limits(db: AsyncSession, tenant: Tenant) -> Dict[str, Any]:
    from Services.platform_license_service import get_active_license

    limits: Dict[str, Any] = {
        "max_users": 100000,
        "max_buildings": 1000,
        "max_flats": 100000,
        "storage_gb": 5000,
        "api_rpm": 10000,
    }
    sub = await get_active_subscription(db, tenant.id)
    if sub and sub.get("plan"):
        for k, v in (sub["plan"].get("limits") or {}).items():
            limits[k] = v
    lic = await get_active_license(db, tenant.id)
    if lic:
        for k, v in (lic.get("limits") or {}).items():
            if k in limits:
                limits[k] = min(int(limits[k]), int(v))
            else:
                limits[k] = v
    return limits
