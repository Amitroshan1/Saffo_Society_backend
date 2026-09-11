"""Integration gateway — /api/integrations/v1/* and platform admin integration APIs."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import PLATFORM_ROLES
from Dependencies.auth import CurrentUser, get_current_user, require_roles
from Dependencies.platform_auth import require_platform_read, require_platform_write
from Database.session import get_db
from Schemas.integration import (
    ApiClientCreate,
    ApiKeyCreate,
    CommSendRequest,
    IdentityLinkRequest,
    PaymentIntentCreate,
    PaymentRefundRequest,
    ProviderHealthUpdate,
    PushSendRequest,
    WebhookSubscriptionCreate,
    WebhookSubscriptionUpdate,
)
from Services import integration_admin_service as admin
from Services import mobile_device_service as devices
from Services import payment_orchestrator_service as payments
from Services import webhook_service as webhooks
from Utils.responses import success_response

integrations_router = APIRouter(
    prefix="/api/integrations/v1", tags=["Integrations"]
)
platform_integrations_router = APIRouter(
    prefix="/api/v1/platform/integrations", tags=["Platform Integrations"]
)


# ── Public/provider ingress ─────────────────────────────────────────────────


@integrations_router.post("/webhooks/{provider}")
async def inbound_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_timestamp: Optional[str] = Header(default=None, alias="X-Timestamp"),
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
):
    body = (await request.body()).decode("utf-8")
    data = await webhooks.receive_inbound(
        db,
        provider=provider,
        body=body,
        timestamp=x_timestamp,
        signature=x_signature,
        secret=x_webhook_secret or "",
    )
    await db.commit()
    return success_response(200, "Webhook received", data)


@integrations_router.post("/payments/{provider}/webhooks")
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = (await request.body()).decode("utf-8")
    headers = {k.lower(): v for k, v in request.headers.items()}
    import json

    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}
    external_id = (
        payload.get("externalId")
        or payload.get("external_id")
        or (payload.get("data") or {}).get("id")
    )
    event_type = payload.get("event") or payload.get("type") or "payment.captured"
    data = await payments.handle_provider_webhook(
        db,
        provider_code=provider,
        headers=headers,
        body=body,
        external_id=external_id,
        event_type=event_type,
    )
    await db.commit()
    return success_response(200, "Payment webhook processed", data)


@integrations_router.get("/health")
async def integrations_health(db: AsyncSession = Depends(get_db)):
    await admin.ensure_default_providers(db)
    await db.commit()
    return success_response(200, "OK", {"surface": "integrations"})


# ── Platform admin surfaces ─────────────────────────────────────────────────


@platform_integrations_router.get("/providers")
async def list_providers(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await admin.list_providers(db, category=category)
    await db.commit()
    return success_response(200, "OK", {"providers": rows})


@platform_integrations_router.post("/providers/probe")
async def probe_providers(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    rows = await admin.probe_all_providers(db)
    await db.commit()
    return success_response(200, "Providers probed", {"providers": rows})


@platform_integrations_router.patch("/providers/{provider_id}/health")
async def patch_provider_health(
    provider_id: UUID,
    body: ProviderHealthUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await admin.update_provider_health(
        db, provider_id, status=body.status, detail=body.detail
    )
    await db.commit()
    return success_response(200, "Updated", data)


@platform_integrations_router.get("/webhooks/subscriptions")
async def list_webhook_subs(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await webhooks.list_subscriptions(db)
    return success_response(200, "OK", {"subscriptions": rows})


@platform_integrations_router.post("/webhooks/subscriptions")
async def create_webhook_sub(
    body: WebhookSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await webhooks.create_subscription(
        db,
        name=body.name,
        target_url=body.targetUrl,
        events=body.events,
        society_id=body.societyId,
        created_by=current.user_id,
        max_attempts=body.maxAttempts,
        timeout_seconds=body.timeoutSeconds,
    )
    await db.commit()
    return success_response(200, "Subscription created", data)


@platform_integrations_router.patch("/webhooks/subscriptions/{sub_id}")
async def update_webhook_sub(
    sub_id: UUID,
    body: WebhookSubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await webhooks.update_subscription(
        db,
        sub_id,
        name=body.name,
        target_url=body.targetUrl,
        events=body.events,
        status=body.status,
    )
    await db.commit()
    return success_response(200, "Updated", data)


@platform_integrations_router.post("/webhooks/subscriptions/{sub_id}/test")
async def test_webhook_sub(
    sub_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await webhooks.test_subscription(db, sub_id)
    await db.commit()
    return success_response(200, "Test sent", data)


@platform_integrations_router.get("/webhooks/deliveries")
async def list_webhook_deliveries(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await webhooks.list_deliveries(db)
    return success_response(200, "OK", {"deliveries": rows})


@platform_integrations_router.get("/webhooks/dlq")
async def list_webhook_dlq(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await webhooks.list_dlq(db)
    return success_response(200, "OK", {"items": rows})


@platform_integrations_router.post("/webhooks/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await webhooks.attempt_delivery(db, delivery_id)
    await db.commit()
    return success_response(200, "Retry attempted", data)


@platform_integrations_router.get("/api-clients")
async def list_clients(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await admin.list_api_clients(db)
    return success_response(200, "OK", {"clients": rows})


@platform_integrations_router.post("/api-clients")
async def create_client(
    body: ApiClientCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await admin.create_api_client(
        db,
        name=body.name,
        client_code=body.clientCode,
        scopes=body.scopes,
        society_id=body.societyId,
        description=body.description,
        rate_limit_rpm=body.rateLimitRpm,
        created_by=current.user_id,
    )
    await db.commit()
    return success_response(200, "Client created", data)


@platform_integrations_router.get("/api-keys")
async def list_keys(
    clientId: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await admin.list_api_keys(db, client_id=clientId)
    return success_response(200, "OK", {"keys": rows})


@platform_integrations_router.post("/api-keys")
async def create_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await admin.create_api_key(
        db,
        client_id=body.clientId,
        name=body.name,
        scopes=body.scopes,
        created_by=current.user_id,
    )
    await db.commit()
    return success_response(200, "API key created", data)


@platform_integrations_router.post("/api-keys/{key_id}/revoke")
async def revoke_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await admin.revoke_api_key(db, key_id, actor_id=current.user_id)
    await db.commit()
    return success_response(200, "API key revoked", data)


@platform_integrations_router.get("/devices")
async def list_devices(
    societyId: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await devices.list_devices(db, society_id=societyId)
    return success_response(200, "OK", {"devices": rows})


@platform_integrations_router.post("/devices/{device_id}/remove")
async def remove_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    data = await devices.remove_device(db, device_id, actor_id=current.user_id)
    await db.commit()
    return success_response(200, "Device removed", data)


@platform_integrations_router.get("/payments/intents")
async def list_payment_intents(
    societyId: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await payments.list_intents(db, society_id=societyId)
    return success_response(200, "OK", {"intents": rows})


@platform_integrations_router.post("/payments/reconcile")
async def reconcile_payments(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await payments.reconcile_intents(db)
    return success_response(200, "OK", data)


@platform_integrations_router.post("/payments/intents/{intent_id}/refund")
async def refund_intent(
    intent_id: UUID,
    body: PaymentRefundRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await payments.refund_payment_intent(
        db, intent_id=intent_id, amount_minor=body.amountMinor
    )
    await db.commit()
    return success_response(200, "Refunded", data)


@platform_integrations_router.get("/identity-links")
async def identity_links(
    userId: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    rows = await admin.list_identity_links(db, user_id=userId)
    return success_response(200, "OK", {"links": rows})


@platform_integrations_router.post("/identity-links")
async def create_identity_link(
    body: IdentityLinkRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_platform_write),
):
    # Platform linking for a target requires subject; for self-link use mobile later
    data = await admin.link_identity(
        db,
        user_id=current.user_id,
        provider=body.provider,
        subject=body.subject,
        email=body.email,
        profile=body.profile,
    )
    await db.commit()
    return success_response(200, "Identity linked", data)


@platform_integrations_router.post("/push/send")
async def push_send(
    body: PushSendRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await admin.send_push_to_device(
        db,
        device_id=body.deviceId,
        title=body.title,
        body=body.body,
        data=body.data,
        rich=body.rich,
        silent=body.silent,
        emergency=body.emergency,
    )
    await db.commit()
    return success_response(200, "Push sent", data)


@platform_integrations_router.post("/comm/send")
async def comm_send(
    body: CommSendRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_write),
):
    data = await admin.send_via_provider(
        db, provider_code=body.providerCode, message=body.message
    )
    return success_response(200, "Queued", data)


@platform_integrations_router.get("/metrics")
async def integration_metrics(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_platform_read),
):
    data = await admin.integration_metrics_summary(db)
    return success_response(200, "OK", data)


@platform_integrations_router.get("/storage/health")
async def storage_health(_: CurrentUser = Depends(require_platform_read)):
    from Services.integration_admin_service import STORAGE_ADAPTERS

    return success_response(200, "OK",
        {
            "adapters": [a.health() for a in STORAGE_ADAPTERS.values()],
        },
    )
