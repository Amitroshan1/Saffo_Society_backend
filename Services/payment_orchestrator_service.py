"""Payment provider adapters + orchestrator — settles into Phase 10 records (no billing rewrite)."""

from __future__ import annotations

import secrets
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.integration import PaymentProviderIntent
from Models.maintenance_bill import MaintenanceBill
from Services.integration_helpers import emit_integration_event, iso, utcnow
from Utils.errors import ApiError


class PaymentPort(Protocol):
    code: str

    def create_checkout(
        self, *, amount_minor: int, currency: str, metadata: dict[str, Any]
    ) -> dict[str, Any]: ...

    def verify_webhook(self, *, headers: dict[str, str], body: str) -> bool: ...

    def refund(self, *, external_id: str, amount_minor: int) -> dict[str, Any]: ...


class _BaseAdapter:
    code = "base"

    def create_checkout(
        self, *, amount_minor: int, currency: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        external_id = f"{self.code}_{secrets.token_hex(8)}"
        return {
            "externalId": external_id,
            "checkoutUrl": f"https://pay.example/{self.code}/checkout/{external_id}",
            "clientSecret": secrets.token_urlsafe(24),
            "status": "created",
            "providerPayload": {"simulated": True, "metadata": metadata},
        }

    def verify_webhook(self, *, headers: dict[str, str], body: str) -> bool:
        # MVP: accept when signature header present or X-Simulated-Webhook=1
        return bool(headers.get("x-signature") or headers.get("x-simulated-webhook") == "1")

    def refund(self, *, external_id: str, amount_minor: int) -> dict[str, Any]:
        return {"externalId": external_id, "status": "refunded", "amountMinor": amount_minor}


class RazorpayAdapter(_BaseAdapter):
    code = "razorpay"


class StripeAdapter(_BaseAdapter):
    code = "stripe"


class PayPalAdapter(_BaseAdapter):
    code = "paypal"


class UpiAdapter(_BaseAdapter):
    code = "upi"


ADAPTERS: dict[str, PaymentPort] = {
    "razorpay": RazorpayAdapter(),
    "stripe": StripeAdapter(),
    "paypal": PayPalAdapter(),
    "upi": UpiAdapter(),
}


def get_payment_adapter(code: str) -> PaymentPort:
    adapter = ADAPTERS.get((code or "").lower())
    if not adapter:
        raise ApiError(400, f"Unsupported payment provider: {code}")
    return adapter


def intent_to_dict(intent: PaymentProviderIntent) -> dict[str, Any]:
    return {
        "id": str(intent.id),
        "societyId": str(intent.society_id),
        "userId": str(intent.user_id) if intent.user_id else None,
        "billId": str(intent.bill_id) if intent.bill_id else None,
        "paymentId": str(intent.payment_id) if intent.payment_id else None,
        "providerCode": intent.provider_code,
        "externalId": intent.external_id,
        "amountMinor": intent.amount_minor,
        "currency": intent.currency,
        "status": intent.status,
        "checkoutUrl": intent.checkout_url,
        "clientSecret": intent.client_secret,
        "capturedAt": iso(intent.captured_at),
        "refundedAt": iso(intent.refunded_at),
        "createdAt": iso(intent.created_at),
    }


async def create_payment_intent(
    db: AsyncSession,
    *,
    society_id: UUID,
    user_id: UUID,
    bill_id: UUID,
    provider_code: str,
    idempotency_key: Optional[str] = None,
) -> dict[str, Any]:
    if idempotency_key:
        existing = (
            await db.execute(
                select(PaymentProviderIntent).where(
                    PaymentProviderIntent.idempotency_key == idempotency_key,
                    PaymentProviderIntent.society_id == society_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return intent_to_dict(existing)

    bill = await db.get(MaintenanceBill, bill_id)
    if not bill or bill.society_id != society_id:
        raise ApiError(404, "Bill not found")

    amount = int(getattr(bill, "outstanding_minor", None) or getattr(bill, "net_minor", 0) or 0)
    if amount <= 0:
        raise ApiError(400, "Bill has no outstanding amount")

    adapter = get_payment_adapter(provider_code)
    checkout = adapter.create_checkout(
        amount_minor=amount,
        currency=getattr(bill, "currency", None) or "INR",
        metadata={"billId": str(bill_id), "societyId": str(society_id)},
    )
    intent = PaymentProviderIntent(
        society_id=society_id,
        user_id=user_id,
        bill_id=bill_id,
        provider_code=adapter.code,
        external_id=checkout["externalId"],
        amount_minor=amount,
        currency=getattr(bill, "currency", None) or "INR",
        status="created",
        checkout_url=checkout.get("checkoutUrl"),
        client_secret=checkout.get("clientSecret"),
        provider_payload_json=checkout.get("providerPayload") or {},
        idempotency_key=idempotency_key,
    )
    db.add(intent)
    await db.flush()
    emit_integration_event(
        "PaymentIntentCreated",
        society_id=society_id,
        entity_type="payment_provider_intent",
        entity_id=intent.id,
        actor_id=user_id,
        payload={
            "provider": adapter.code,
            "billId": str(bill_id),
            "amountMinor": amount,
            "externalId": intent.external_id,
        },
    )
    return intent_to_dict(intent)


async def confirm_payment_intent(
    db: AsyncSession,
    *,
    external_id: str,
    provider_code: Optional[str] = None,
) -> dict[str, Any]:
    q = select(PaymentProviderIntent).where(PaymentProviderIntent.external_id == external_id)
    if provider_code:
        q = q.where(PaymentProviderIntent.provider_code == provider_code.lower())
    intent = (await db.execute(q)).scalar_one_or_none()
    if not intent:
        raise ApiError(404, "Payment intent not found")
    if intent.status == "captured":
        return intent_to_dict(intent)

    # Link placeholder payment_id (Phase 10 record creation remains billing service responsibility)
    intent.status = "captured"
    intent.captured_at = utcnow()
    intent.payment_id = intent.payment_id or uuid4()
    await db.flush()
    emit_integration_event(
        "PaymentCaptured",
        society_id=intent.society_id,
        entity_type="payment_provider_intent",
        entity_id=intent.id,
        payload={
            "provider": intent.provider_code,
            "externalId": intent.external_id,
            "paymentId": str(intent.payment_id),
            "billId": str(intent.bill_id) if intent.bill_id else None,
        },
    )
    return intent_to_dict(intent)


async def refund_payment_intent(
    db: AsyncSession, *, intent_id: UUID, amount_minor: Optional[int] = None
) -> dict[str, Any]:
    intent = await db.get(PaymentProviderIntent, intent_id)
    if not intent:
        raise ApiError(404, "Payment intent not found")
    if intent.status not in ("captured", "partially_refunded"):
        raise ApiError(400, "Only captured payments can be refunded")
    adapter = get_payment_adapter(intent.provider_code)
    refund_amount = amount_minor or intent.amount_minor
    adapter.refund(external_id=intent.external_id, amount_minor=refund_amount)
    intent.status = "refunded"
    intent.refunded_at = utcnow()
    await db.flush()
    emit_integration_event(
        "PaymentRefunded",
        society_id=intent.society_id,
        entity_type="payment_provider_intent",
        entity_id=intent.id,
        payload={"externalId": intent.external_id, "amountMinor": refund_amount},
    )
    return intent_to_dict(intent)


async def handle_provider_webhook(
    db: AsyncSession,
    *,
    provider_code: str,
    headers: dict[str, str],
    body: str,
    external_id: Optional[str] = None,
    event_type: str = "payment.captured",
) -> dict[str, Any]:
    adapter = get_payment_adapter(provider_code)
    if not adapter.verify_webhook(headers=headers, body=body):
        raise ApiError(401, "Invalid payment webhook signature")
    if event_type.endswith("captured") or event_type.endswith("paid"):
        if not external_id:
            raise ApiError(400, "external_id required")
        return await confirm_payment_intent(
            db, external_id=external_id, provider_code=provider_code
        )
    return {"accepted": True, "eventType": event_type}


async def list_intents(
    db: AsyncSession, *, society_id: Optional[UUID] = None, limit: int = 50
) -> list[dict[str, Any]]:
    q = select(PaymentProviderIntent).order_by(PaymentProviderIntent.created_at.desc()).limit(limit)
    if society_id:
        q = q.where(PaymentProviderIntent.society_id == society_id)
    rows = (await db.execute(q)).scalars().all()
    return [intent_to_dict(r) for r in rows]


async def reconcile_intents(db: AsyncSession) -> dict[str, Any]:
    """Nightly-style reconciliation skeleton: count gaps (captured without payment_id)."""
    rows = (
        await db.execute(
            select(PaymentProviderIntent).where(
                PaymentProviderIntent.status == "captured",
                PaymentProviderIntent.payment_id.is_(None),
            )
        )
    ).scalars().all()
    return {
        "gaps": len(rows),
        "intentIds": [str(r.id) for r in rows[:50]],
        "checkedAt": iso(utcnow()),
    }
