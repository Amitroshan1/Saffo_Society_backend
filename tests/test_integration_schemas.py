"""Phase 18 integration / mobile unit tests (no DB required for most)."""

import pytest
from pydantic import ValidationError

from Schemas.integration import (
    ApiClientCreate,
    DeviceRegisterRequest,
    MobileLoginRequest,
    PaymentIntentCreate,
    WebhookSubscriptionCreate,
)
from Services.integration_helpers import (
    DEFAULT_PROVIDERS,
    DEEP_LINK_ROUTES,
    hmac_sign,
    hmac_verify,
    hash_secret,
    generate_api_key,
)
from Services.mobile_hub_service import hub_capabilities, resolve_deep_link
from Services.payment_orchestrator_service import ADAPTERS, get_payment_adapter
from Services.sync_service import ALLOWED_MUTATIONS, SERVER_AUTHORITATIVE
from Utils.errors import ApiError


def test_default_providers_catalog():
    codes = {p["code"] for p in DEFAULT_PROVIDERS}
    assert "razorpay" in codes
    assert "stripe" in codes
    assert "fcm" in codes
    assert "minio" in codes
    assert "google_oauth" in codes
    assert len(DEFAULT_PROVIDERS) >= 20


def test_hmac_roundtrip():
    secret = "test-secret"
    ts = "1700000000"
    body = '{"ok":true}'
    sig = hmac_sign(secret, ts, body)
    assert hmac_verify(secret, ts, body, sig, max_skew_sec=10**12)


def test_hmac_rejects_bad_signature():
    assert not hmac_verify("s", "1700000000", "{}", "deadbeef", max_skew_sec=10**12)


def test_api_key_generation():
    raw, prefix, hashed = generate_api_key()
    assert raw.startswith("sms_")
    assert len(prefix) >= 8
    assert hashed == hash_secret(raw)


def test_device_register_schema():
    body = DeviceRegisterRequest(deviceUid="dev-123", platform="android", appId="resident")
    assert body.platform == "android"


def test_mobile_login_schema():
    body = MobileLoginRequest(
        email="r@x.com",
        password="Admin@123",
        deviceUid="d1",
        platform="ios",
    )
    assert body.deviceUid == "d1"


def test_webhook_subscription_schema():
    body = WebhookSubscriptionCreate(
        name="ERP",
        targetUrl="https://example.com/hooks",
        events=["BillIssued"],
    )
    assert "BillIssued" in body.events


def test_api_client_code_validation():
    with pytest.raises(ValidationError):
        ApiClientCreate(name="Bad", clientCode="bad code!", scopes=[])


def test_payment_adapters_registered():
    assert set(ADAPTERS.keys()) >= {"razorpay", "stripe", "paypal", "upi"}
    adapter = get_payment_adapter("razorpay")
    checkout = adapter.create_checkout(amount_minor=100, currency="INR", metadata={})
    assert checkout["externalId"].startswith("razorpay_")


def test_unknown_payment_adapter():
    with pytest.raises(ApiError):
        get_payment_adapter("unknown_psp")


def test_sync_policy_classes():
    assert "payments" in SERVER_AUTHORITATIVE
    assert "approve" in ALLOWED_MUTATIONS["visits"]
    assert "mark_read" in ALLOWED_MUTATIONS["notices"]


def test_deep_link_resolve():
    data = resolve_deep_link(link_type="bill", entity_id="abc")
    assert data["resolved"] is True
    assert "abc" in data["path"]
    assert "notice" in DEEP_LINK_ROUTES


def test_hub_capabilities_roles():
    assert "bills" in hub_capabilities("resident")["capabilities"]
    assert "visitor_entry" in hub_capabilities("guard")["capabilities"]
    assert "collections" in hub_capabilities("finance")["capabilities"]


def test_payment_intent_schema():
    from uuid import uuid4

    body = PaymentIntentCreate(billId=uuid4(), providerCode="stripe")
    assert body.providerCode == "stripe"
