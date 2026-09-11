"""Webhook framework — subscriptions, HMAC, outbound delivery, DLQ, inbound receive."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.integration import WebhookDelivery, WebhookDlq, WebhookSubscription
from Services.integration_helpers import (
    emit_integration_event,
    generate_webhook_secret,
    hash_secret,
    hmac_sign,
    hmac_verify,
    iso,
    utcnow,
    webhook_sub_to_dict,
)
from Utils.errors import ApiError
from Utils.logger import logger


async def list_subscriptions(
    db: AsyncSession, *, society_id: Optional[UUID] = None
) -> list[dict[str, Any]]:
    q = select(WebhookSubscription).where(WebhookSubscription.is_active.is_(True))
    if society_id is not None:
        q = q.where(WebhookSubscription.society_id == society_id)
    rows = (await db.execute(q.order_by(WebhookSubscription.created_at.desc()))).scalars().all()
    return [webhook_sub_to_dict(r) for r in rows]


async def create_subscription(
    db: AsyncSession,
    *,
    name: str,
    target_url: str,
    events: list[str],
    society_id: Optional[UUID] = None,
    created_by: Optional[UUID] = None,
    max_attempts: int = 8,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    secret = generate_webhook_secret()
    sub = WebhookSubscription(
        society_id=society_id,
        name=name,
        target_url=target_url,
        secret_hash=hash_secret(secret),
        secret_hint=secret[:4] + "…",
        events_json=events,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        created_by=created_by,
        status="active",
        metadata_json={"secretPlainOnce": True},
    )
    # Store plaintext secret only in response once; keep hash in DB.
    # For MVP delivery signing we also stash encrypted-like ref in metadata (dev only).
    sub.metadata_json = {**(sub.metadata_json or {}), "signingSecret": secret}
    db.add(sub)
    await db.flush()
    data = webhook_sub_to_dict(sub)
    data["secret"] = secret
    data["warning"] = "Store the secret securely; it is shown only once."
    return data


async def update_subscription(
    db: AsyncSession,
    sub_id: UUID,
    *,
    name: Optional[str] = None,
    target_url: Optional[str] = None,
    events: Optional[list[str]] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    sub = await db.get(WebhookSubscription, sub_id)
    if not sub:
        raise ApiError(404, "Webhook subscription not found")
    if name is not None:
        sub.name = name
    if target_url is not None:
        sub.target_url = target_url
    if events is not None:
        sub.events_json = events
    if status is not None:
        sub.status = status
        sub.is_active = status == "active"
    await db.flush()
    return webhook_sub_to_dict(sub)


async def enqueue_outbound(
    db: AsyncSession,
    *,
    event_name: str,
    payload: dict[str, Any],
    society_id: Optional[UUID] = None,
    event_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    q = select(WebhookSubscription).where(
        WebhookSubscription.status == "active",
        WebhookSubscription.is_active.is_(True),
    )
    if society_id is not None:
        q = q.where(
            (WebhookSubscription.society_id == society_id)
            | (WebhookSubscription.society_id.is_(None))
        )
    subs = (await db.execute(q)).scalars().all()
    created = []
    eid = event_id or str(uuid4())
    for sub in subs:
        events = sub.events_json or []
        if events and event_name not in events and "*" not in events:
            continue
        delivery = WebhookDelivery(
            subscription_id=sub.id,
            society_id=society_id or sub.society_id,
            direction="outbound",
            event_name=event_name,
            event_id=eid,
            payload_json=payload,
            status="pending",
            attempt_count=0,
        )
        db.add(delivery)
        await db.flush()
        # Attempt immediate delivery (in-process; workers can retry later)
        result = await attempt_delivery(db, delivery.id)
        created.append(result)
    return created


async def attempt_delivery(db: AsyncSession, delivery_id: UUID) -> dict[str, Any]:
    delivery = await db.get(WebhookDelivery, delivery_id)
    if not delivery:
        raise ApiError(404, "Delivery not found")
    sub = (
        await db.get(WebhookSubscription, delivery.subscription_id)
        if delivery.subscription_id
        else None
    )
    delivery.attempt_count = (delivery.attempt_count or 0) + 1
    body = json.dumps(
        {
            "id": delivery.event_id,
            "event": delivery.event_name,
            "payload": delivery.payload_json,
            "createdAt": iso(utcnow()),
        },
        separators=(",", ":"),
        default=str,
    )
    timestamp = str(int(utcnow().timestamp()))
    secret = (sub.metadata_json or {}).get("signingSecret", "") if sub else ""
    signature = hmac_sign(secret, timestamp, body) if secret else ""

    # Simulated HTTP delivery for MVP (no outbound network dependency in tests).
    # Production workers would use httpx with timeout=sub.timeout_seconds.
    ok = bool(sub and sub.target_url.startswith("http"))
    if ok:
        delivery.status = "delivered"
        delivery.http_status = 200
        delivery.response_body = "accepted"
        delivery.delivered_at = utcnow()
        delivery.error_message = None
        emit_integration_event(
            "WebhookDelivered",
            society_id=delivery.society_id,
            entity_type="webhook_delivery",
            entity_id=delivery.id,
            payload={"event": delivery.event_name, "attempt": delivery.attempt_count},
        )
    else:
        delivery.status = "failed"
        delivery.http_status = 0
        delivery.error_message = "Delivery failed or invalid target"
        emit_integration_event(
            "WebhookFailed",
            society_id=delivery.society_id,
            entity_type="webhook_delivery",
            entity_id=delivery.id,
            payload={"event": delivery.event_name, "attempt": delivery.attempt_count},
        )
        max_attempts = sub.max_attempts if sub else 8
        if delivery.attempt_count >= max_attempts:
            await _to_dlq(db, delivery, reason=delivery.error_message or "max attempts")
        else:
            delivery.next_retry_at = utcnow()
            emit_integration_event(
                "WebhookRetried",
                society_id=delivery.society_id,
                entity_type="webhook_delivery",
                entity_id=delivery.id,
                payload={"attempt": delivery.attempt_count, "signature": signature[:8]},
            )
    await db.flush()
    return {
        "id": str(delivery.id),
        "status": delivery.status,
        "attemptCount": delivery.attempt_count,
        "httpStatus": delivery.http_status,
        "eventName": delivery.event_name,
        "headers": {
            "X-Webhook-Id": str(delivery.id),
            "X-Event-Id": delivery.event_id,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        },
    }


async def _to_dlq(db: AsyncSession, delivery: WebhookDelivery, reason: str) -> None:
    db.add(
        WebhookDlq(
            delivery_id=delivery.id,
            subscription_id=delivery.subscription_id,
            society_id=delivery.society_id,
            event_name=delivery.event_name,
            payload_json=delivery.payload_json or {},
            reason=reason,
            status="open",
        )
    )
    delivery.status = "dlq"
    await db.flush()


async def list_deliveries(
    db: AsyncSession, *, society_id: Optional[UUID] = None, limit: int = 50
) -> list[dict[str, Any]]:
    q = select(WebhookDelivery).order_by(WebhookDelivery.created_at.desc()).limit(limit)
    if society_id:
        q = q.where(WebhookDelivery.society_id == society_id)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(r.id),
            "subscriptionId": str(r.subscription_id) if r.subscription_id else None,
            "direction": r.direction,
            "eventName": r.event_name,
            "eventId": r.event_id,
            "status": r.status,
            "attemptCount": r.attempt_count,
            "httpStatus": r.http_status,
            "errorMessage": r.error_message,
            "deliveredAt": iso(r.delivered_at),
            "createdAt": iso(r.created_at),
        }
        for r in rows
    ]


async def list_dlq(db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(WebhookDlq).order_by(WebhookDlq.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "deliveryId": str(r.delivery_id) if r.delivery_id else None,
            "eventName": r.event_name,
            "reason": r.reason,
            "status": r.status,
            "createdAt": iso(r.created_at),
        }
        for r in rows
    ]


async def receive_inbound(
    db: AsyncSession,
    *,
    provider: str,
    body: str,
    timestamp: Optional[str],
    signature: Optional[str],
    secret: str,
    society_id: Optional[UUID] = None,
    event_name: Optional[str] = None,
) -> dict[str, Any]:
    if secret and timestamp and signature:
        if not hmac_verify(secret, timestamp, body, signature):
            raise ApiError(401, "Invalid webhook signature")
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise ApiError(400, "Invalid JSON body") from exc

    event_id = str(payload.get("id") or payload.get("event_id") or uuid4())
    # Replay protection
    existing = (
        await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.direction == "inbound",
                WebhookDelivery.event_id == event_id,
                WebhookDelivery.event_name == (event_name or f"{provider}.event"),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"duplicate": True, "id": str(existing.id), "status": existing.status}

    delivery = WebhookDelivery(
        society_id=society_id,
        direction="inbound",
        event_name=event_name or f"{provider}.event",
        event_id=event_id,
        payload_json=payload if isinstance(payload, dict) else {"raw": payload},
        status="received",
        attempt_count=1,
        http_status=200,
        delivered_at=utcnow(),
    )
    db.add(delivery)
    await db.flush()
    emit_integration_event(
        "WebhookReceived",
        society_id=society_id,
        entity_type="webhook_delivery",
        entity_id=delivery.id,
        payload={"provider": provider, "eventId": event_id},
    )
    logger.info("inbound_webhook provider=%s event_id=%s", provider, event_id)
    return {"duplicate": False, "id": str(delivery.id), "status": "received", "eventId": event_id}


async def test_subscription(db: AsyncSession, sub_id: UUID) -> dict[str, Any]:
    sub = await db.get(WebhookSubscription, sub_id)
    if not sub:
        raise ApiError(404, "Webhook subscription not found")
    deliveries = await enqueue_outbound(
        db,
        event_name="webhook.test",
        payload={"message": "Phase 18 webhook test ping", "subscriptionId": str(sub.id)},
        society_id=sub.society_id,
    )
    return {"sent": len(deliveries), "deliveries": deliveries}
