"""Feature flag engine."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.platform import FeatureFlag, Tenant, TenantFeatureFlag
from Services.platform_helpers import (
    DEFAULT_FEATURE_FLAGS,
    emit_platform_event,
    utcnow,
    write_audit,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError

_feature_cache: Dict[str, tuple[float, Dict[str, bool]]] = {}
CACHE_TTL_SEC = 45.0


def _cache_key(tenant_id: UUID | None) -> str:
    return str(tenant_id) if tenant_id else "__global__"


def invalidate_feature_cache(tenant_id: UUID | None = None) -> None:
    if tenant_id is None:
        _feature_cache.clear()
    else:
        _feature_cache.pop(_cache_key(tenant_id), None)
        _feature_cache.pop("__global__", None)


async def ensure_default_flags(db: AsyncSession, actor_id: UUID | None = None) -> None:
    existing = {
        r.key
        for r in (await db.execute(select(FeatureFlag))).scalars().all()
    }
    for d in DEFAULT_FEATURE_FLAGS:
        if d["key"] in existing:
            continue
        row = FeatureFlag(
            key=d["key"],
            name=d["name"],
            description=d.get("description"),
            default_enabled=d.get("default_enabled", True),
            tags_json=d.get("tags_json") or [],
        )
        if actor_id:
            apply_create_audit(row, actor_id)
        db.add(row)
    await db.flush()


def flag_to_dict(f: FeatureFlag) -> dict:
    return {
        "id": str(f.id),
        "key": f.key,
        "name": f.name,
        "description": f.description,
        "defaultEnabled": f.default_enabled,
        "rolloutPercent": f.rollout_percent,
        "tags": f.tags_json or [],
        "isActive": f.is_active,
    }


async def list_flags(db: AsyncSession) -> List[dict]:
    await ensure_default_flags(db)
    rows = (await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all()
    return [flag_to_dict(r) for r in rows]


async def upsert_flag(
    db: AsyncSession,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    key = body["key"].strip()
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    row = result.scalar_one_or_none()
    before = flag_to_dict(row) if row else None
    if not row:
        row = FeatureFlag(key=key, name=body.get("name") or key)
        apply_create_audit(row, actor_id)
        db.add(row)
    else:
        apply_update_audit(row, actor_id)
    if "name" in body and body["name"]:
        row.name = body["name"]
    if "description" in body:
        row.description = body["description"]
    if "defaultEnabled" in body and body["defaultEnabled"] is not None:
        row.default_enabled = bool(body["defaultEnabled"])
    if "rolloutPercent" in body and body["rolloutPercent"] is not None:
        row.rollout_percent = int(body["rolloutPercent"])
    if "tags" in body and body["tags"] is not None:
        row.tags_json = body["tags"]
    await db.flush()
    after = flag_to_dict(row)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="feature_flag.upsert",
        resource_type="feature_flag",
        resource_id=row.key,
        before=before,
        after=after,
    )
    emit_platform_event(
        "FeatureFlagChanged",
        entity_type="feature_flag",
        entity_id=row.id,
        actor_id=actor_id,
        payload={"key": row.key},
    )
    invalidate_feature_cache()
    await db.commit()
    await db.refresh(row)
    return flag_to_dict(row)


async def set_tenant_overrides(
    db: AsyncSession,
    tenant_id: UUID,
    overrides: List[Dict[str, Any]],
    *,
    actor_id: UUID,
    actor_role: str,
) -> List[dict]:
    from Services.platform_tenant_service import resolve_tenant

    await resolve_tenant(db, tenant_id)
    out = []
    for item in overrides:
        key = item["key"]
        mode = item.get("mode") or "inherit"
        if mode not in ("on", "off", "inherit"):
            raise ApiError(422, "mode must be on|off|inherit")
        result = await db.execute(
            select(TenantFeatureFlag).where(
                TenantFeatureFlag.tenant_id == tenant_id,
                TenantFeatureFlag.flag_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            row = TenantFeatureFlag(tenant_id=tenant_id, flag_key=key, mode=mode)
            apply_create_audit(row, actor_id)
            db.add(row)
        else:
            row.mode = mode
            apply_update_audit(row, actor_id)
        out.append({"key": key, "mode": mode})
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="tenant_feature_flags.set",
        resource_type="tenant",
        resource_id=str(tenant_id),
        tenant_id=tenant_id,
        after={"overrides": out},
    )
    emit_platform_event(
        "FeatureFlagChanged",
        tenant_id=tenant_id,
        entity_type="tenant",
        entity_id=tenant_id,
        actor_id=actor_id,
        payload={"overrides": out},
    )
    invalidate_feature_cache(tenant_id)
    await db.commit()
    return out


async def apply_plan_features_to_tenant(
    db: AsyncSession, tenant: Tenant, *, actor_id: UUID
) -> None:
    """Write inherit overrides; resolution uses plan features separately."""
    await ensure_default_flags(db, actor_id)
    await db.flush()


async def _plan_features(db: AsyncSession, tenant: Tenant) -> Dict[str, bool]:
    from Models.platform import SubscriptionPlan, TenantSubscription

    sub_q = await db.execute(
        select(TenantSubscription)
        .where(
            TenantSubscription.tenant_id == tenant.id,
            TenantSubscription.is_active.is_(True),
            TenantSubscription.status.in_(("trialing", "active", "past_due", "grace")),
        )
        .order_by(TenantSubscription.created_at.desc())
        .limit(1)
    )
    sub = sub_q.scalar_one_or_none()
    if not sub:
        return {}
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
    ).scalar_one_or_none()
    if not plan:
        return {}
    return {k: bool(v) for k, v in (plan.features_json or {}).items()}


async def resolve_features_for_tenant(
    db: AsyncSession, tenant: Tenant
) -> Dict[str, bool]:
    import time

    key = _cache_key(tenant.id)
    cached = _feature_cache.get(key)
    now = time.time()
    if cached and now - cached[0] < CACHE_TTL_SEC:
        return dict(cached[1])

    await ensure_default_flags(db)
    flags = (await db.execute(select(FeatureFlag).where(FeatureFlag.is_active.is_(True)))).scalars().all()
    plan_feats = await _plan_features(db, tenant)
    overrides = {
        o.flag_key: o.mode
        for o in (
            await db.execute(
                select(TenantFeatureFlag).where(
                    TenantFeatureFlag.tenant_id == tenant.id,
                    TenantFeatureFlag.is_active.is_(True),
                )
            )
        ).scalars().all()
    }

    resolved: Dict[str, bool] = {}
    for f in flags:
        enabled = f.default_enabled
        if f.key in plan_feats:
            enabled = plan_feats[f.key]
        mode = overrides.get(f.key)
        if mode == "on":
            enabled = True
        elif mode == "off":
            enabled = False
        resolved[f.key] = enabled

    _feature_cache[key] = (now, dict(resolved))
    return resolved


async def resolve_features_for_society(
    db: AsyncSession, society_id: UUID
) -> Dict[str, bool]:
    from Services.platform_tenant_service import resolve_tenant_by_society

    tenant = await resolve_tenant_by_society(db, society_id)
    if not tenant:
        # No tenant record — all defaults on
        await ensure_default_flags(db)
        flags = (await db.execute(select(FeatureFlag))).scalars().all()
        return {f.key: f.default_enabled for f in flags}
    return await resolve_features_for_tenant(db, tenant)


async def is_feature_enabled(
    db: AsyncSession, society_id: UUID | None, flag_key: str
) -> bool:
    if not society_id:
        return True
    feats = await resolve_features_for_society(db, society_id)
    return bool(feats.get(flag_key, True))
