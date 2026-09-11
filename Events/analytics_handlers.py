"""Domain event subscribers for analytics incremental facts (Phase 16)."""

from __future__ import annotations

import asyncio
from datetime import date

from Database.session import AsyncSessionLocal
from Events.bus import DomainEvent, subscribe
from Services import analytics_service
from Utils.logger import logger

EVENT_METRIC_MAP = {
    "BillPublished": "billing.billed.month",
    "PaymentReceived": "billing.revenue.day",
    "BillOverdue": "billing.overdue.amount",
    "ComplaintCreated": "complaint.open.count",
    "ComplaintResolved": "complaint.resolved.month",
    "VisitorCheckedIn": "visitor.checkins.day",
    "VisitorCheckedOut": "visitor.checkins.day",
    "NoticePublished": "notice.published.count",
    "NoticeRead": "notice.reads.count",
    "BookingApproved": "amenity.bookings.day",
    "BookingCheckedIn": "amenity.bookings.day",
    "ParkingAllocated": "parking.slots.allocated",
    "VehicleEntry": "visitor.checkins.day",
    "VisitorParkingCreated": "parking.slots.allocated",
    "NotificationDelivered": "notification.unread.count",
    "DocumentDownloaded": "document.published.count",
    "DocumentCreated": "document.published.count",
}


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)


async def _handle_event(event: DomainEvent) -> None:
    if not event.society_id:
        return
    metric = EVENT_METRIC_MAP.get(event.name)
    if not metric:
        return
    async with AsyncSessionLocal() as db:
        try:
            delta = 1
            if event.name in ("VisitorCheckedOut",):
                delta = 0
            if delta:
                await analytics_service.increment_metric(
                    db, event.society_id, metric, delta=delta, grain_date=date.today()
                )
            await db.commit()
        except Exception:
            logger.exception(
                "analytics_handler failed event=%s society=%s",
                event.name,
                event.society_id,
            )
            await db.rollback()


def _sync_handler(event: DomainEvent) -> None:
    _schedule(_handle_event(event))


def register_analytics_handlers() -> None:
    for name in EVENT_METRIC_MAP:
        subscribe(name, _sync_handler)
    logger.info("Registered %s analytics event handlers", len(EVENT_METRIC_MAP))
