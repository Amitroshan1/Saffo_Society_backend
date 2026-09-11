"""Communication, push, storage, identity, API key, and provider admin services."""

from __future__ import annotations

import secrets
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.integration import (
    ApiClient,
    ApiKey,
    IdentityLink,
    IntegrationCredential,
    IntegrationProvider,
    MobileCrashReport,
    MobileDevice,
    StorageObject,
)
from Services.integration_helpers import (
    DEFAULT_PROVIDERS,
    api_client_to_dict,
    api_key_to_dict,
    emit_integration_event,
    generate_api_key,
    hash_secret,
    iso,
    provider_to_dict,
    utcnow,
)
from Utils.errors import ApiError


# ── Providers ──────────────────────────────────────────────────────────────


async def ensure_default_providers(db: AsyncSession) -> int:
    created = 0
    for item in DEFAULT_PROVIDERS:
        existing = (
            await db.execute(
                select(IntegrationProvider).where(IntegrationProvider.code == item["code"])
            )
        ).scalar_one_or_none()
        if existing:
            continue
        db.add(
            IntegrationProvider(
                code=item["code"],
                name=item["name"],
                category=item["category"],
                adapter_key=item["adapter_key"],
                is_platform_default=bool(item.get("is_platform_default")),
                health_status="unknown",
                status="active",
            )
        )
        created += 1
    if created:
        await db.flush()
    return created


async def list_providers(
    db: AsyncSession, *, category: Optional[str] = None
) -> list[dict[str, Any]]:
    await ensure_default_providers(db)
    q = select(IntegrationProvider).order_by(IntegrationProvider.category, IntegrationProvider.code)
    if category:
        q = q.where(IntegrationProvider.category == category)
    rows = (await db.execute(q)).scalars().all()
    return [provider_to_dict(r) for r in rows]


async def update_provider_health(
    db: AsyncSession, provider_id: UUID, *, status: str, detail: Optional[str] = None
) -> dict[str, Any]:
    p = await db.get(IntegrationProvider, provider_id)
    if not p:
        raise ApiError(404, "Provider not found")
    p.health_status = status
    p.health_detail = detail
    p.last_health_at = utcnow()
    await db.flush()
    emit_integration_event(
        "ProviderHealthChanged",
        entity_type="integration_provider",
        entity_id=p.id,
        payload={"code": p.code, "healthStatus": status, "detail": detail},
    )
    return provider_to_dict(p)


async def probe_all_providers(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_default_providers(db)
    rows = (await db.execute(select(IntegrationProvider))).scalars().all()
    out = []
    for p in rows:
        # Adapter health probe (simulated OK for registered adapters)
        status = "up" if p.is_active else "down"
        p.health_status = status
        p.health_detail = "ok" if status == "up" else "inactive"
        p.last_health_at = utcnow()
        out.append(provider_to_dict(p))
        emit_integration_event(
            "ProviderHealthChanged",
            entity_type="integration_provider",
            entity_id=p.id,
            payload={"code": p.code, "healthStatus": status},
        )
    await db.flush()
    return out


# ── Communication adapters (invoked by Phase 15 workers) ───────────────────


class CommAdapter:
    def __init__(self, code: str):
        self.code = code

    def send(self, message: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": self.code,
            "providerMessageId": f"{self.code}_{secrets.token_hex(6)}",
            "status": "queued",
            "simulated": True,
        }

    def health(self) -> dict[str, Any]:
        return {"provider": self.code, "status": "up"}


COMM_ADAPTERS = {
    "smtp": CommAdapter("smtp"),
    "ses": CommAdapter("ses"),
    "twilio": CommAdapter("twilio"),
    "msg91": CommAdapter("msg91"),
    "whatsapp": CommAdapter("whatsapp"),
    "fcm": CommAdapter("fcm"),
    "apns": CommAdapter("apns"),
    "onesignal": CommAdapter("onesignal"),
}


def get_comm_adapter(code: str) -> CommAdapter:
    adapter = COMM_ADAPTERS.get(code)
    if not adapter:
        raise ApiError(400, f"Unknown communication adapter: {code}")
    return adapter


async def send_via_provider(
    db: AsyncSession, *, provider_code: str, message: dict[str, Any]
) -> dict[str, Any]:
    await ensure_default_providers(db)
    adapter = get_comm_adapter(provider_code)
    result = adapter.send(message)
    return result


# ── Push ────────────────────────────────────────────────────────────────────


async def send_push_to_device(
    db: AsyncSession,
    *,
    device_id: UUID,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    rich: bool = False,
    silent: bool = False,
    emergency: bool = False,
) -> dict[str, Any]:
    device = await db.get(MobileDevice, device_id)
    if not device or not device.push_token:
        raise ApiError(404, "Device push token not registered")
    provider = device.push_provider or "fcm"
    adapter = get_comm_adapter(provider if provider in COMM_ADAPTERS else "fcm")
    payload = {
        "token": device.push_token,
        "title": title,
        "body": body,
        "data": data or {},
        "rich": rich,
        "silent": silent,
        "emergency": emergency,
    }
    try:
        result = adapter.send(payload)
        emit_integration_event(
            "PushDelivered",
            society_id=device.society_id,
            entity_type="mobile_device",
            entity_id=device.id,
            payload={"provider": provider, "title": title},
        )
        return {"status": "sent", **result}
    except Exception as exc:
        emit_integration_event(
            "PushFailed",
            society_id=device.society_id,
            entity_type="mobile_device",
            entity_id=device.id,
            payload={"provider": provider, "error": str(exc)},
        )
        raise


async def subscribe_topic(device_id: UUID, topic: str) -> dict[str, Any]:
    return {"deviceId": str(device_id), "topic": topic, "status": "subscribed"}


# ── Storage port ────────────────────────────────────────────────────────────


class StorageAdapter:
    def __init__(self, code: str, bucket: str = "sms-uploads"):
        self.code = code
        self.bucket = bucket

    def mint_upload(self, object_key: str, content_type: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(24)
        return {
            "provider": self.code,
            "bucket": self.bucket,
            "objectKey": object_key,
            "uploadUrl": f"https://storage.example/{self.code}/{self.bucket}/{object_key}?token={token}",
            "uploadToken": token,
            "headers": {"Content-Type": content_type},
            "expiresInSeconds": 900,
        }

    def signed_download(self, object_key: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(16)
        return {
            "provider": self.code,
            "downloadUrl": f"https://cdn.example/{self.bucket}/{object_key}?sig={token}",
            "cdnUrl": f"https://cdn.example/{self.bucket}/{object_key}",
            "expiresInSeconds": 600,
        }

    def health(self) -> dict[str, Any]:
        return {"provider": self.code, "status": "up"}


STORAGE_ADAPTERS = {
    "s3": StorageAdapter("s3"),
    "azure_blob": StorageAdapter("azure_blob"),
    "gcs": StorageAdapter("gcs"),
    "minio": StorageAdapter("minio"),
}


def get_storage_adapter(code: str = "minio") -> StorageAdapter:
    adapter = STORAGE_ADAPTERS.get(code or "minio")
    if not adapter:
        raise ApiError(400, f"Unknown storage adapter: {code}")
    return adapter


async def mint_upload_token(
    db: AsyncSession,
    *,
    society_id: Optional[UUID],
    user_id: Optional[UUID],
    module: str = "general",
    filename: str,
    content_type: str = "application/octet-stream",
    provider_code: str = "minio",
) -> dict[str, Any]:
    adapter = get_storage_adapter(provider_code)
    safe_name = filename.replace(" ", "_")
    object_key = f"tenant/{society_id or 'platform'}/{module}/{utcnow().year}/{utcnow().month:02d}/{uuid4()}_{safe_name}"
    minted = adapter.mint_upload(object_key, content_type)
    obj = StorageObject(
        society_id=society_id,
        user_id=user_id,
        module=module,
        provider_code=adapter.code,
        bucket=minted["bucket"],
        object_key=object_key,
        content_type=content_type,
        status="pending",
        cdn_url=None,
        metadata_json={"filename": filename},
    )
    db.add(obj)
    await db.flush()
    emit_integration_event(
        "StorageUploadCompleted",
        society_id=society_id,
        entity_type="storage_object",
        entity_id=obj.id,
        actor_id=user_id,
        payload={"objectKey": object_key, "status": "token_minted"},
    )
    return {
        "storageObjectId": str(obj.id),
        **minted,
    }


async def mint_download_url(
    db: AsyncSession, *, storage_object_id: UUID, user_id: Optional[UUID] = None
) -> dict[str, Any]:
    obj = await db.get(StorageObject, storage_object_id)
    if not obj:
        raise ApiError(404, "Storage object not found")
    adapter = get_storage_adapter(obj.provider_code)
    signed = adapter.signed_download(obj.object_key)
    obj.cdn_url = signed.get("cdnUrl")
    obj.status = "available"
    await db.flush()
    emit_integration_event(
        "StorageDownloadRequested",
        society_id=obj.society_id,
        entity_type="storage_object",
        entity_id=obj.id,
        actor_id=user_id,
        payload={"objectKey": obj.object_key},
    )
    return {"storageObjectId": str(obj.id), **signed}


# ── Identity links ──────────────────────────────────────────────────────────


async def link_identity(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider: str,
    subject: str,
    email: Optional[str] = None,
    profile: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    existing = (
        await db.execute(
            select(IdentityLink).where(
                IdentityLink.provider == provider.lower(),
                IdentityLink.subject == subject,
            )
        )
    ).scalar_one_or_none()
    if existing and existing.user_id != user_id:
        raise ApiError(409, "Identity already linked to another user")
    if existing:
        existing.status = "active"
        existing.unlinked_at = None
        existing.email = email or existing.email
        existing.profile_json = profile or existing.profile_json
        link = existing
    else:
        link = IdentityLink(
            user_id=user_id,
            provider=provider.lower(),
            subject=subject,
            email=email,
            profile_json=profile or {},
            status="active",
        )
        db.add(link)
    await db.flush()
    emit_integration_event(
        "IdentityLinked",
        entity_type="identity_link",
        entity_id=link.id,
        actor_id=user_id,
        payload={"provider": provider, "subject": subject},
    )
    return {
        "id": str(link.id),
        "userId": str(link.user_id),
        "provider": link.provider,
        "subject": link.subject,
        "email": link.email,
        "status": link.status,
    }


async def unlink_identity(db: AsyncSession, *, link_id: UUID, user_id: UUID) -> dict[str, Any]:
    link = await db.get(IdentityLink, link_id)
    if not link or link.user_id != user_id:
        raise ApiError(404, "Identity link not found")
    link.status = "unlinked"
    link.unlinked_at = utcnow()
    await db.flush()
    emit_integration_event(
        "IdentityUnlinked",
        entity_type="identity_link",
        entity_id=link.id,
        actor_id=user_id,
        payload={"provider": link.provider},
    )
    return {"id": str(link.id), "status": "unlinked"}


async def list_identity_links(
    db: AsyncSession, *, user_id: Optional[UUID] = None
) -> list[dict[str, Any]]:
    q = select(IdentityLink).order_by(IdentityLink.linked_at.desc())
    if user_id:
        q = q.where(IdentityLink.user_id == user_id)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(r.id),
            "userId": str(r.user_id),
            "provider": r.provider,
            "subject": r.subject,
            "email": r.email,
            "status": r.status,
            "linkedAt": iso(r.linked_at),
        }
        for r in rows
    ]


# ── API clients / keys ──────────────────────────────────────────────────────


async def create_api_client(
    db: AsyncSession,
    *,
    name: str,
    client_code: str,
    scopes: list[str],
    society_id: Optional[UUID] = None,
    description: Optional[str] = None,
    rate_limit_rpm: int = 120,
    created_by: Optional[UUID] = None,
) -> dict[str, Any]:
    existing = (
        await db.execute(select(ApiClient).where(ApiClient.client_code == client_code))
    ).scalar_one_or_none()
    if existing:
        raise ApiError(409, "Client code already exists")
    client = ApiClient(
        society_id=society_id,
        name=name,
        client_code=client_code,
        description=description,
        scopes_json=scopes,
        rate_limit_rpm=rate_limit_rpm,
        created_by=created_by,
        status="active",
    )
    db.add(client)
    await db.flush()
    return api_client_to_dict(client)


async def list_api_clients(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(ApiClient).order_by(ApiClient.created_at.desc()))
    ).scalars().all()
    return [api_client_to_dict(r) for r in rows]


async def create_api_key(
    db: AsyncSession,
    *,
    client_id: UUID,
    name: str = "default",
    scopes: Optional[list[str]] = None,
    created_by: Optional[UUID] = None,
) -> dict[str, Any]:
    client = await db.get(ApiClient, client_id)
    if not client:
        raise ApiError(404, "API client not found")
    raw, prefix, key_hash = generate_api_key()
    key = ApiKey(
        client_id=client_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes_json=scopes if scopes is not None else (client.scopes_json or []),
        created_by=created_by,
        status="active",
    )
    db.add(key)
    await db.flush()
    emit_integration_event(
        "APIKeyCreated",
        society_id=client.society_id,
        entity_type="api_key",
        entity_id=key.id,
        actor_id=created_by,
        payload={"clientId": str(client_id), "prefix": prefix},
    )
    return api_key_to_dict(key, raw_key=raw)


async def revoke_api_key(
    db: AsyncSession, key_id: UUID, *, actor_id: Optional[UUID] = None
) -> dict[str, Any]:
    key = await db.get(ApiKey, key_id)
    if not key:
        raise ApiError(404, "API key not found")
    key.status = "revoked"
    key.revoked_at = utcnow()
    await db.flush()
    client = await db.get(ApiClient, key.client_id)
    emit_integration_event(
        "APIKeyRevoked",
        society_id=client.society_id if client else None,
        entity_type="api_key",
        entity_id=key.id,
        actor_id=actor_id,
        payload={"prefix": key.key_prefix},
    )
    return api_key_to_dict(key)


async def list_api_keys(
    db: AsyncSession, *, client_id: Optional[UUID] = None
) -> list[dict[str, Any]]:
    q = select(ApiKey).order_by(ApiKey.created_at.desc())
    if client_id:
        q = q.where(ApiKey.client_id == client_id)
    rows = (await db.execute(q)).scalars().all()
    return [api_key_to_dict(r) for r in rows]


async def verify_api_key(db: AsyncSession, raw_key: str) -> Optional[dict[str, Any]]:
    key = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == hash_secret(raw_key),
                ApiKey.status == "active",
            )
        )
    ).scalar_one_or_none()
    if not key:
        return None
    if key.expires_at and key.expires_at < utcnow():
        return None
    key.last_used_at = utcnow()
    client = await db.get(ApiClient, key.client_id)
    return {
        "keyId": str(key.id),
        "clientId": str(key.client_id),
        "scopes": key.scopes_json or [],
        "societyId": str(client.society_id) if client and client.society_id else None,
        "rateLimitRpm": client.rate_limit_rpm if client else 120,
    }


# ── Crash reports ───────────────────────────────────────────────────────────


async def ingest_crash_report(
    db: AsyncSession,
    *,
    message: str,
    society_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    device_id: Optional[UUID] = None,
    app_id: Optional[str] = None,
    app_version: Optional[str] = None,
    platform: Optional[str] = None,
    stack_hash: Optional[str] = None,
    breadcrumbs: Optional[list] = None,
) -> dict[str, Any]:
    # PII scrub: keep message short
    clean = (message or "crash")[:512]
    report = MobileCrashReport(
        society_id=society_id,
        user_id=user_id,
        device_id=device_id,
        app_id=app_id,
        app_version=app_version,
        platform=platform,
        message=clean,
        stack_hash=stack_hash,
        breadcrumbs_json=(breadcrumbs or [])[:20],
    )
    db.add(report)
    await db.flush()
    return {"id": str(report.id), "accepted": True}


async def integration_metrics_summary(db: AsyncSession) -> dict[str, Any]:
    providers = (await db.execute(select(IntegrationProvider))).scalars().all()
    devices = (await db.execute(select(MobileDevice))).scalars().all()
    keys = (await db.execute(select(ApiKey).where(ApiKey.status == "active"))).scalars().all()
    return {
        "providers": len(providers),
        "providersUp": sum(1 for p in providers if p.health_status == "up"),
        "devices": len(devices),
        "activeDevices": sum(1 for d in devices if d.status == "active"),
        "activeApiKeys": len(keys),
        "checkedAt": iso(utcnow()),
    }
