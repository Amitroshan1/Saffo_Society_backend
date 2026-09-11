"""Shared helpers for Phase 17 platform control plane."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.platform import PlatformAuditLog, PlatformJobRun

DEFAULT_FEATURE_FLAGS = [
    {
        "key": "module.parking",
        "name": "Parking",
        "description": "Parking management module",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.amenities",
        "name": "Amenities",
        "description": "Amenities booking module",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.notifications",
        "name": "Notifications",
        "description": "Notifications & communication",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.analytics",
        "name": "Analytics",
        "description": "Reports & analytics",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.documents",
        "name": "Documents",
        "description": "Document management",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.billing",
        "name": "Billing",
        "description": "Society billing & accounting",
        "default_enabled": True,
        "tags_json": ["module"],
    },
    {
        "key": "module.ai_assistant",
        "name": "AI Assistant",
        "description": "Future AI assistant",
        "default_enabled": False,
        "tags_json": ["experimental"],
    },
    {
        "key": "module.visitor_qr",
        "name": "Visitor QR",
        "description": "Visitor QR features",
        "default_enabled": True,
        "tags_json": ["module"],
    },
]

DEFAULT_PLANS = [
    {
        "code": "trial",
        "name": "Trial",
        "billing_period": "trial",
        "price_minor": 0,
        "trial_days": 14,
        "limits_json": {
            "max_users": 25,
            "max_buildings": 2,
            "max_flats": 50,
            "storage_gb": 5,
            "api_rpm": 120,
        },
        "features_json": {
            "module.parking": True,
            "module.amenities": True,
            "module.notifications": True,
            "module.analytics": True,
            "module.documents": True,
            "module.billing": True,
            "module.ai_assistant": False,
            "module.visitor_qr": True,
        },
        "sort_order": 1,
    },
    {
        "code": "monthly",
        "name": "Monthly",
        "billing_period": "monthly",
        "price_minor": 499900,
        "trial_days": 0,
        "limits_json": {
            "max_users": 200,
            "max_buildings": 10,
            "max_flats": 500,
            "storage_gb": 50,
            "api_rpm": 600,
        },
        "features_json": {
            "module.parking": True,
            "module.amenities": True,
            "module.notifications": True,
            "module.analytics": True,
            "module.documents": True,
            "module.billing": True,
            "module.ai_assistant": False,
            "module.visitor_qr": True,
        },
        "sort_order": 2,
    },
    {
        "code": "yearly",
        "name": "Yearly",
        "billing_period": "yearly",
        "price_minor": 4999000,
        "trial_days": 0,
        "limits_json": {
            "max_users": 500,
            "max_buildings": 25,
            "max_flats": 2000,
            "storage_gb": 200,
            "api_rpm": 1200,
        },
        "features_json": {
            "module.parking": True,
            "module.amenities": True,
            "module.notifications": True,
            "module.analytics": True,
            "module.documents": True,
            "module.billing": True,
            "module.ai_assistant": False,
            "module.visitor_qr": True,
        },
        "sort_order": 3,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "billing_period": "enterprise",
        "price_minor": 0,
        "trial_days": 0,
        "limits_json": {
            "max_users": 100000,
            "max_buildings": 1000,
            "max_flats": 100000,
            "storage_gb": 5000,
            "api_rpm": 10000,
        },
        "features_json": {
            "module.parking": True,
            "module.amenities": True,
            "module.notifications": True,
            "module.analytics": True,
            "module.documents": True,
            "module.billing": True,
            "module.ai_assistant": True,
            "module.visitor_qr": True,
        },
        "sort_order": 4,
        "is_public": False,
    },
]

SETTING_GROUPS = (
    "branding",
    "smtp",
    "sms",
    "push",
    "storage",
    "backups",
    "cache",
    "queue",
    "security",
    "defaults",
    "email_templates",
)

SECRET_REF_KEYS = {
    "smtp": ["password_env"],
    "sms": ["auth_token_env"],
    "push": ["server_key_env"],
    "storage": ["secret_access_key_env"],
    "cache": ["password_env"],
    "queue": ["password_env"],
}

FEATURE_PATH_PREFIXES = (
    ("/api/v1/parking", "module.parking"),
    ("/api/v1/facilities", "module.amenities"),
    ("/api/v1/amenity", "module.amenities"),
    ("/api/v1/notifications", "module.notifications"),
    ("/api/v1/analytics", "module.analytics"),
    ("/api/v1/documents", "module.documents"),
    ("/api/v1/billing", "module.billing"),
)

TENANT_STATUSES = (
    "draft",
    "provisioning",
    "active",
    "suspended",
    "archived",
    "pending_delete",
    "provisioning_failed",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def generate_license_key() -> str:
    return f"LIC-{secrets.token_hex(16).upper()}"


def generate_temp_password() -> str:
    return f"Tmp@{secrets.token_hex(4)}A1!"


def emit_platform_event(
    name: str,
    *,
    tenant_id: UUID | None = None,
    society_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    payload: dict | None = None,
) -> None:
    data = dict(payload or {})
    if tenant_id:
        data["tenantId"] = str(tenant_id)
    publish_simple(
        name,
        society_id=society_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        payload=data,
    )


async def write_audit(
    db: AsyncSession,
    *,
    actor_user_id: UUID | None,
    actor_role: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    tenant_id: UUID | None = None,
    before: Any = None,
    after: Any = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PlatformAuditLog:
    row = PlatformAuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        tenant_id=tenant_id,
        before_json=before if isinstance(before, dict) else None,
        after_json=after if isinstance(after, dict) else None,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(row)
    await db.flush()
    return row


async def start_job(db: AsyncSession, job_key: str) -> PlatformJobRun:
    row = PlatformJobRun(
        job_key=job_key,
        status="running",
        started_at=utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def finish_job(
    db: AsyncSession,
    row: PlatformJobRun,
    *,
    status: str = "succeeded",
    result: dict | None = None,
    error: str | None = None,
) -> None:
    row.status = status
    row.finished_at = utcnow()
    if row.started_at:
        row.duration_ms = int((row.finished_at - row.started_at).total_seconds() * 1000)
    row.result_json = result or {}
    row.error_message = error
    await db.flush()


def tenant_to_dict(t) -> dict:
    return {
        "id": str(t.id),
        "societyId": str(t.society_id) if t.society_id else None,
        "name": t.name,
        "code": t.code,
        "displayName": t.display_name or t.name,
        "status": t.status,
        "isolationMode": t.isolation_mode,
        "region": t.region,
        "timezone": t.timezone,
        "adminEmail": t.admin_email,
        "planCode": t.plan_code,
        "provisionedAt": iso(t.provisioned_at),
        "suspendedAt": iso(t.suspended_at),
        "archivedAt": iso(t.archived_at),
        "deleteAfter": iso(t.delete_after),
        "notes": t.notes,
        "isActive": t.is_active,
        "createdAt": iso(t.created_at),
        "updatedAt": iso(t.updated_at),
    }


def plan_to_dict(p) -> dict:
    return {
        "id": str(p.id),
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "billingPeriod": p.billing_period,
        "priceMinor": p.price_minor,
        "currency": p.currency,
        "trialDays": p.trial_days,
        "limits": p.limits_json or {},
        "features": p.features_json or {},
        "isPublic": p.is_public,
        "sortOrder": p.sort_order,
        "isActive": p.is_active,
        "createdAt": iso(p.created_at),
    }


def subscription_to_dict(s) -> dict:
    return {
        "id": str(s.id),
        "tenantId": str(s.tenant_id),
        "planId": str(s.plan_id),
        "status": s.status,
        "billingPeriod": s.billing_period,
        "startsAt": iso(s.starts_at),
        "endsAt": iso(s.ends_at),
        "trialEndsAt": iso(s.trial_ends_at),
        "graceEndsAt": iso(s.grace_ends_at),
        "cancelledAt": iso(s.cancelled_at),
        "autoRenew": s.auto_renew,
        "externalRef": s.external_ref,
        "isActive": s.is_active,
        "createdAt": iso(s.created_at),
    }


def license_to_dict(lic) -> dict:
    return {
        "id": str(lic.id),
        "tenantId": str(lic.tenant_id),
        "licenseKey": lic.license_key,
        "status": lic.status,
        "issuedAt": iso(lic.issued_at),
        "expiresAt": iso(lic.expires_at),
        "limits": lic.limits_json or {},
        "features": lic.features_json or {},
        "isActive": lic.is_active,
        "createdAt": iso(lic.created_at),
    }
