"""Global platform settings + maintenance mode."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.platform import PlatformMaintenanceWindow, PlatformSetting
from Services.platform_helpers import (
    SETTING_GROUPS,
    SECRET_REF_KEYS,
    emit_platform_event,
    iso,
    utcnow,
    write_audit,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError

_settings_cache: Dict[str, Any] = {}
_maintenance_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _mask_secrets(group: str, values: dict, secret_refs: dict) -> dict:
    out = dict(values or {})
    for key in (SECRET_REF_KEYS.get(group) or []):
        if key in out and out[key]:
            out[key] = "***"
        env_name = (secret_refs or {}).get(key)
        if env_name:
            out[f"{key}Configured"] = True
            out[key] = f"${{{env_name}}}"
    # never return password-like plaintext
    for k in list(out.keys()):
        lk = k.lower()
        if any(x in lk for x in ("password", "secret", "token", "api_key", "apikey")):
            if out[k] and not str(out[k]).startswith("${"):
                out[k] = "***"
    return out


def setting_to_dict(row: PlatformSetting) -> dict:
    return {
        "id": str(row.id),
        "group": row.group_key,
        "values": _mask_secrets(row.group_key, row.values_json or {}, row.secret_refs_json or {}),
        "secretRefs": row.secret_refs_json or {},
        "isActive": row.is_active,
        "updatedAt": iso(row.updated_at),
    }


async def ensure_default_settings(db: AsyncSession, actor_id: UUID | None = None) -> None:
    existing = {
        r.group_key
        for r in (await db.execute(select(PlatformSetting))).scalars().all()
    }
    defaults = {
        "branding": {
            "platformName": "Society Management Platform",
            "primaryColor": "#0F766E",
            "logoUrl": "",
        },
        "smtp": {"host": "", "port": 587, "fromAddress": "", "username": ""},
        "sms": {"provider": "twilio", "fromNumber": ""},
        "push": {"provider": "firebase"},
        "storage": {"provider": "s3", "bucket": "", "region": ""},
        "backups": {"retentionDays": 30, "scheduleCron": "0 2 * * *"},
        "cache": {"provider": "redis", "defaultTtlSeconds": 60},
        "queue": {"provider": "redis"},
        "security": {
            "platformSessionMinutes": 30,
            "mfaRequiredPlatform": False,
            "impersonationMinutes": 30,
        },
        "defaults": {"timezone": "Asia/Kolkata", "currency": "INR", "language": "en"},
        "email_templates": {},
    }
    for group in SETTING_GROUPS:
        if group in existing:
            continue
        row = PlatformSetting(
            group_key=group,
            values_json=defaults.get(group, {}),
            secret_refs_json={k: k.upper() for k in (SECRET_REF_KEYS.get(group) or [])},
        )
        if actor_id:
            apply_create_audit(row, actor_id)
        db.add(row)
    await db.flush()


async def list_settings(db: AsyncSession) -> List[dict]:
    await ensure_default_settings(db)
    rows = (
        await db.execute(select(PlatformSetting).order_by(PlatformSetting.group_key))
    ).scalars().all()
    return [setting_to_dict(r) for r in rows]


async def get_settings_group(db: AsyncSession, group: str) -> dict:
    await ensure_default_settings(db)
    if group not in SETTING_GROUPS:
        raise ApiError(404, "Unknown settings group")
    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.group_key == group)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Settings not found")
    return setting_to_dict(row)


async def patch_settings_group(
    db: AsyncSession,
    group: str,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    await ensure_default_settings(db, actor_id)
    if group not in SETTING_GROUPS:
        raise ApiError(404, "Unknown settings group")
    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.group_key == group)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Settings not found")
    before = setting_to_dict(row)
    values = dict(row.values_json or {})
    incoming = body.get("values") or {}
    # Strip plaintext secrets — only accept env ref updates
    for k, v in incoming.items():
        lk = k.lower()
        if any(x in lk for x in ("password", "secret", "token", "api_key")) and v and v != "***":
            if not str(v).startswith("${") and k not in (SECRET_REF_KEYS.get(group) or []):
                # treat as env var name reference
                refs = dict(row.secret_refs_json or {})
                refs[k] = str(v)
                row.secret_refs_json = refs
                continue
            if str(v) == "***":
                continue
        values[k] = v
    row.values_json = values
    if "secretRefs" in body and isinstance(body["secretRefs"], dict):
        row.secret_refs_json = body["secretRefs"]
    apply_update_audit(row, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="settings.update",
        resource_type="platform_settings",
        resource_id=group,
        before=before,
        after=setting_to_dict(row),
    )
    _settings_cache.clear()
    await db.commit()
    await db.refresh(row)
    return setting_to_dict(row)


async def get_maintenance(db: AsyncSession) -> dict:
    import time

    now = time.time()
    if _maintenance_cache["data"] and now - _maintenance_cache["ts"] < 15:
        return dict(_maintenance_cache["data"])

    result = await db.execute(
        select(PlatformMaintenanceWindow)
        .order_by(PlatformMaintenanceWindow.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        data = {
            "enabled": False,
            "message": "Platform under maintenance",
            "allowPlatformAdmin": True,
        }
    else:
        data = {
            "id": str(row.id),
            "enabled": row.enabled,
            "message": row.message,
            "allowPlatformAdmin": row.allow_platform_admin,
            "startedAt": iso(row.started_at),
            "endedAt": iso(row.ended_at),
        }
    _maintenance_cache["ts"] = now
    _maintenance_cache["data"] = data
    return data


async def set_maintenance(
    db: AsyncSession,
    *,
    enabled: bool,
    message: str | None,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    result = await db.execute(
        select(PlatformMaintenanceWindow)
        .order_by(PlatformMaintenanceWindow.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        row = PlatformMaintenanceWindow(enabled=False)
        apply_create_audit(row, actor_id)
        db.add(row)
        await db.flush()
    row.enabled = enabled
    if message:
        row.message = message
    if enabled:
        row.started_at = utcnow()
        row.ended_at = None
    else:
        row.ended_at = utcnow()
    apply_update_audit(row, actor_id)
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="maintenance.toggle",
        resource_type="maintenance",
        resource_id=str(row.id),
        after={"enabled": enabled, "message": row.message},
    )
    emit_platform_event(
        "MaintenanceModeEnabled" if enabled else "MaintenanceModeDisabled",
        entity_type="maintenance",
        entity_id=row.id,
        actor_id=actor_id,
        payload={"message": row.message},
    )
    _maintenance_cache["data"] = None
    await db.commit()
    return await get_maintenance(db)
