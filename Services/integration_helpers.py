"""Phase 18 shared helpers — providers catalog, events, serializers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from Events.bus import publish_simple

DEFAULT_PROVIDERS = [
    {"code": "razorpay", "name": "Razorpay", "category": "payment", "adapter_key": "razorpay"},
    {"code": "stripe", "name": "Stripe", "category": "payment", "adapter_key": "stripe"},
    {"code": "paypal", "name": "PayPal", "category": "payment", "adapter_key": "paypal"},
    {"code": "upi", "name": "UPI", "category": "payment", "adapter_key": "upi"},
    {"code": "smtp", "name": "SMTP", "category": "email", "adapter_key": "smtp"},
    {"code": "ses", "name": "Amazon SES", "category": "email", "adapter_key": "ses"},
    {"code": "twilio", "name": "Twilio SMS", "category": "sms", "adapter_key": "twilio"},
    {"code": "msg91", "name": "MSG91", "category": "sms", "adapter_key": "msg91"},
    {"code": "fcm", "name": "Firebase Cloud Messaging", "category": "push", "adapter_key": "fcm"},
    {"code": "apns", "name": "Apple Push Notification", "category": "push", "adapter_key": "apns"},
    {"code": "onesignal", "name": "OneSignal", "category": "push", "adapter_key": "onesignal"},
    {"code": "whatsapp", "name": "WhatsApp Business", "category": "messaging", "adapter_key": "whatsapp"},
    {"code": "s3", "name": "AWS S3", "category": "storage", "adapter_key": "s3"},
    {"code": "azure_blob", "name": "Azure Blob", "category": "storage", "adapter_key": "azure_blob"},
    {"code": "gcs", "name": "Google Cloud Storage", "category": "storage", "adapter_key": "gcs"},
    {"code": "minio", "name": "MinIO", "category": "storage", "adapter_key": "minio", "is_platform_default": True},
    {"code": "google_oauth", "name": "Google Login", "category": "identity", "adapter_key": "google"},
    {"code": "microsoft_oauth", "name": "Microsoft Login", "category": "identity", "adapter_key": "microsoft"},
    {"code": "apple_oauth", "name": "Apple Login", "category": "identity", "adapter_key": "apple"},
    {"code": "ldap", "name": "LDAP", "category": "identity", "adapter_key": "ldap"},
    {"code": "saml", "name": "SAML SSO", "category": "identity", "adapter_key": "saml"},
    {"code": "erp_generic", "name": "Generic ERP", "category": "erp", "adapter_key": "rest"},
    {"code": "crm_generic", "name": "Generic CRM", "category": "crm", "adapter_key": "rest"},
    {"code": "accounting_generic", "name": "Generic Accounting", "category": "accounting", "adapter_key": "rest"},
    {"code": "gov_generic", "name": "Government API", "category": "government", "adapter_key": "rest"},
]

MOBILE_APP_CONFIG = {
    "minBuild": {"android": 1, "ios": 1},
    "minOs": {"android": "8.0", "ios": "14.0"},
    "deepLinkScheme": "smsapp",
    "forceUpdate": False,
    "maintenanceBanner": None,
    "features": {
        "offlineSync": True,
        "biometricLogin": True,
        "push": True,
        "payments": True,
    },
}

DEEP_LINK_ROUTES = {
    "notice": "/resident/notices/{id}",
    "bill": "/resident/bills/{id}",
    "visit": "/resident/visitors",
    "complaint": "/resident/complaints",
    "document": "/resident/documents/{id}",
    "booking": "/resident/bookings/{id}",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw = f"sms_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, hash_secret(raw)


def generate_webhook_secret() -> str:
    return secrets.token_urlsafe(32)


def hmac_sign(secret: str, timestamp: str, body: str) -> str:
    message = f"{timestamp}.{body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def hmac_verify(secret: str, timestamp: str, body: str, signature: str, max_skew_sec: int = 300) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > max_skew_sec:
        return False
    expected = hmac_sign(secret, timestamp, body)
    return hmac.compare_digest(expected, signature or "")


def emit_integration_event(
    name: str,
    *,
    society_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    actor_id: Optional[UUID] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    publish_simple(
        name,
        society_id=society_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        payload=payload or {},
    )


def device_to_dict(d) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "userId": str(d.user_id) if d.user_id else None,
        "societyId": str(d.society_id) if d.society_id else None,
        "deviceUid": d.device_uid,
        "platform": d.platform,
        "appId": d.app_id,
        "appVersion": d.app_version,
        "osVersion": d.os_version,
        "pushToken": d.push_token,
        "pushProvider": d.push_provider,
        "biometricEnabled": d.biometric_enabled,
        "status": d.status,
        "lastSeenAt": iso(d.last_seen_at),
        "createdAt": iso(d.created_at),
    }


def provider_to_dict(p) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "code": p.code,
        "name": p.name,
        "category": p.category,
        "adapterKey": p.adapter_key,
        "status": p.status,
        "healthStatus": p.health_status,
        "healthDetail": p.health_detail,
        "lastHealthAt": iso(p.last_health_at),
        "configJson": p.config_json or {},
        "scopesJson": p.scopes_json or [],
        "isPlatformDefault": p.is_platform_default,
        "isActive": p.is_active,
    }


def webhook_sub_to_dict(s) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "societyId": str(s.society_id) if s.society_id else None,
        "name": s.name,
        "targetUrl": s.target_url,
        "secretHint": s.secret_hint,
        "events": s.events_json or [],
        "status": s.status,
        "maxAttempts": s.max_attempts,
        "timeoutSeconds": s.timeout_seconds,
        "isActive": s.is_active,
        "createdAt": iso(s.created_at),
    }


def api_client_to_dict(c) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "societyId": str(c.society_id) if c.society_id else None,
        "name": c.name,
        "clientCode": c.client_code,
        "description": c.description,
        "scopes": c.scopes_json or [],
        "status": c.status,
        "rateLimitRpm": c.rate_limit_rpm,
        "isActive": c.is_active,
        "createdAt": iso(c.created_at),
    }


def api_key_to_dict(k, *, raw_key: Optional[str] = None) -> dict[str, Any]:
    data = {
        "id": str(k.id),
        "clientId": str(k.client_id),
        "name": k.name,
        "keyPrefix": k.key_prefix,
        "scopes": k.scopes_json or [],
        "status": k.status,
        "lastUsedAt": iso(k.last_used_at),
        "expiresAt": iso(k.expires_at),
        "revokedAt": iso(k.revoked_at),
        "createdAt": iso(k.created_at),
    }
    if raw_key:
        data["apiKey"] = raw_key
        data["warning"] = "Store this key securely; it will not be shown again."
    return data
