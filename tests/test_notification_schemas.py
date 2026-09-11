"""Notification schema validation tests (no DB)."""

import pytest
from pydantic import ValidationError

from Schemas.notification import (
    BroadcastRequest,
    InvoiceNotificationRequest,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    PaymentReminderRequest,
    PreferenceUpdate,
    ReceiptNotificationRequest,
    ScheduleNotificationRequest,
    validate_channels,
    validate_placeholders,
    render_template,
)

VALID_UUID = "00000000-0000-0000-0000-000000000001"


def test_template_create_normalizes_code():
    body = NotificationTemplateCreate(
        code=" PAY-REM ",
        name="Payment Reminder",
        category="billing",
        channel="email",
        bodyTemplate="Dear {{resident_name}}, pay {{amount}} for {{invoice_number}}.",
    )
    assert body.code == "pay_rem"
    assert body.category == "billing"


def test_template_create_rejects_unknown_placeholder():
    with pytest.raises(ValidationError):
        NotificationTemplateCreate(
            code="bad",
            name="Bad",
            category="system",
            channel="in_app",
            bodyTemplate="Hello {{unknown_field}}",
        )


def test_validate_placeholders_ok():
    assert (
        validate_placeholders("Hi {{resident_name}} from {{society_name}}")
        == "Hi {{resident_name}} from {{society_name}}"
    )


def test_guard_notification_placeholders_ok():
    text = "SOS {{complaint_title}} visitor {{visitor_name}} shift {{shift_type}} on {{shift_date}} for {{purpose}}"
    assert validate_placeholders(text) == text


def test_validate_channels_requires_one():
    with pytest.raises(ValueError):
        validate_channels([])


def test_broadcast_requires_content_or_template():
    with pytest.raises(ValidationError):
        BroadcastRequest(targetType="society", channels=["in_app"])


def test_broadcast_role_requires_target_role():
    with pytest.raises(ValidationError):
        BroadcastRequest(
            title="Hello",
            body="World",
            targetType="role",
            channels=["in_app"],
        )


def test_broadcast_resident_requires_resident_id():
    with pytest.raises(ValidationError):
        BroadcastRequest(
            title="Hello",
            body="World",
            targetType="resident",
            channels=["in_app"],
        )


def test_schedule_requires_future_datetime():
    from datetime import datetime, timedelta, timezone

    future = datetime.now(timezone.utc) + timedelta(days=1)
    body = ScheduleNotificationRequest(
        title="Reminder",
        body="Pay dues",
        targetType="society",
        scheduleAt=future,
    )
    assert body.recurrence is None


def test_template_update_optional_fields():
    body = NotificationTemplateUpdate(name="Updated name", isActive=False)
    assert body.name == "Updated name"
    assert body.isActive is False


def test_payment_reminder_defaults():
    body = PaymentReminderRequest(residentId=VALID_UUID)
    assert "in_app" in body.channels
    assert "email" in body.channels


def test_invoice_notification_channels():
    body = InvoiceNotificationRequest(residentId=VALID_UUID, channels=["sms"])
    assert body.channels == ["sms"]


def test_receipt_notification_variables():
    body = ReceiptNotificationRequest(
        residentId=VALID_UUID,
        amount="1500",
        receiptNumber="RCP-001",
    )
    assert body.amount == "1500"
    assert body.receiptNumber == "RCP-001"


def test_preference_update_partial():
    body = PreferenceUpdate(emailEnabled=False, pushEnabled=True)
    assert body.emailEnabled is False
    assert body.smsEnabled is None


def test_render_template_replaces_placeholders():
    rendered = render_template(
        "Dear {{resident_name}}, flat {{flat}} — {{amount}} due.",
        {"resident_name": "Asha", "flat": "101", "amount": "1500"},
    )
    assert rendered == "Dear Asha, flat 101 — 1500 due."


def test_render_template_missing_keys_become_empty():
    assert render_template("Hello {{resident_name}}", {}) == "Hello "
