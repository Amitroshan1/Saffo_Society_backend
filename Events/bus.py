"""In-process domain event bus — publish only; no notification channels."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, DefaultDict, Dict, List
from uuid import UUID

from Utils.logger import logger


@dataclass
class DomainEvent:
    name: str
    society_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor_id: UUID | None = None
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[DomainEvent], None]

_handlers: DefaultDict[str, List[EventHandler]] = defaultdict(list)


def subscribe(event_name: str, handler: EventHandler) -> None:
    _handlers[event_name].append(handler)


def publish(event: DomainEvent) -> None:
    logger.info(
        "domain_event name=%s society=%s entity=%s/%s",
        event.name,
        event.society_id,
        event.entity_type,
        event.entity_id,
    )
    for handler in list(_handlers.get(event.name, [])):
        try:
            handler(event)
        except Exception:
            logger.exception("domain_event handler failed name=%s", event.name)


def publish_simple(
    name: str,
    *,
    society_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    payload: Dict[str, Any] | None = None,
) -> None:
    publish(
        DomainEvent(
            name=name,
            society_id=society_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            payload=payload or {},
        )
    )
