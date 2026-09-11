"""Phase 18 integration / mobile event handlers."""

from __future__ import annotations

from Events.bus import DomainEvent, subscribe
from Utils.logger import logger

_REGISTERED = False


def _log(event: DomainEvent) -> None:
    logger.info(
        "integration_event name=%s society=%s payload=%s",
        event.name,
        event.society_id,
        {k: (event.payload or {}).get(k) for k in list((event.payload or {}).keys())[:6]},
    )


def register_integration_handlers() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    events = [
        "DeviceRegistered",
        "DeviceRemoved",
        "PushRegistered",
        "PushDelivered",
        "PushFailed",
        "SyncStarted",
        "SyncCompleted",
        "SyncConflict",
        "WebhookReceived",
        "WebhookDelivered",
        "WebhookFailed",
        "WebhookRetried",
        "PaymentIntentCreated",
        "PaymentCaptured",
        "PaymentRefunded",
        "ProviderHealthChanged",
        "StorageUploadCompleted",
        "StorageDownloadRequested",
        "APIKeyCreated",
        "APIKeyRevoked",
        "IdentityLinked",
        "IdentityUnlinked",
        # consume existing domain events (observe only)
        "BillIssued",
        "PaymentRecorded",
        "VisitCheckedIn",
        "NoticePublished",
        "TenantSuspended",
    ]
    for name in events:
        subscribe(name, _log)
    _REGISTERED = True
    logger.info("integration_event_handlers_registered count=%s", len(events))
