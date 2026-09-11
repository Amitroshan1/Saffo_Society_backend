"""Audit field helpers for create/update/version tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def apply_create_audit(entity: Any, actor_id: UUID) -> None:
    now = utcnow()
    if hasattr(entity, "created_by"):
        entity.created_by = actor_id
    if hasattr(entity, "updated_by"):
        entity.updated_by = actor_id
    if hasattr(entity, "last_activity_at"):
        entity.last_activity_at = now
    if hasattr(entity, "version") and getattr(entity, "version", None) is None:
        entity.version = 1


def apply_update_audit(entity: Any, actor_id: UUID) -> None:
    if hasattr(entity, "updated_by"):
        entity.updated_by = actor_id
    if hasattr(entity, "last_activity_at"):
        entity.last_activity_at = utcnow()
    if hasattr(entity, "version"):
        entity.version = (getattr(entity, "version", 0) or 0) + 1
