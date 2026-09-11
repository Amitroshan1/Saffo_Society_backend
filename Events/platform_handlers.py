"""Platform domain event handlers (Phase 17)."""

from __future__ import annotations

from Events.bus import DomainEvent, subscribe
from Utils.logger import logger

_REGISTERED = False


def _log(event: DomainEvent) -> None:
    logger.info(
        "platform_event name=%s tenant=%s society=%s payload=%s",
        event.name,
        (event.payload or {}).get("tenantId"),
        event.society_id,
        {k: event.payload.get(k) for k in list((event.payload or {}).keys())[:6]},
    )


def register_platform_handlers() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    events = [
        "TenantCreated",
        "TenantProvisioned",
        "TenantActivated",
        "TenantSuspended",
        "TenantReactivated",
        "TenantArchived",
        "TenantDeleteScheduled",
        "TenantPurged",
        "TenantImpersonationStarted",
        "TenantImpersonationEnded",
        "DemoTenantCloned",
        "SubscriptionCreated",
        "SubscriptionRenewed",
        "SubscriptionCancelled",
        "LicenseIssued",
        "LicenseRenewed",
        "LicenseDeactivated",
        "LicenseLimitExceeded",
        "FeatureFlagChanged",
        "PlatformAnnouncementCreated",
        "PlatformAnnouncementSent",
        "MaintenanceModeEnabled",
        "MaintenanceModeDisabled",
    ]
    for name in events:
        subscribe(name, _log)
    _REGISTERED = True
    logger.info("platform_event_handlers_registered count=%s", len(events))
