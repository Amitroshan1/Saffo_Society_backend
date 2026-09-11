"""Domain event subscribers for notification enqueue (Phase 15)."""

from __future__ import annotations

import asyncio

from Database.session import AsyncSessionLocal
from Events.bus import DomainEvent, subscribe
from Services import notification_service
from Utils.logger import logger


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)


async def _handle_event(event: DomainEvent) -> None:
    if not event.society_id:
        return
    async with AsyncSessionLocal() as db:
        try:
            await notification_service.process_domain_event(
                db,
                event.name,
                {
                    "society_id": event.society_id,
                    "actor_id": event.actor_id,
                    "payload": event.payload,
                },
            )
        except Exception:
            logger.exception(
                "notification_handler failed event=%s society=%s",
                event.name,
                event.society_id,
            )
            await db.rollback()


def _sync_handler(event: DomainEvent) -> None:
    _schedule(_handle_event(event))


def register_notification_handlers() -> None:
    for event_name in notification_service.EVENT_CONFIG:
        subscribe(event_name, _sync_handler)
    logger.info(
        "Registered %s notification event handlers",
        len(notification_service.EVENT_CONFIG),
    )
