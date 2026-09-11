"""Soft-delete (deactivate) helper for is_active models."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from Utils.audit import apply_update_audit


def soft_deactivate(entity: Any, actor_id: UUID) -> None:
    if hasattr(entity, "is_active"):
        entity.is_active = False
    apply_update_audit(entity, actor_id)


def soft_activate(entity: Any, actor_id: UUID) -> None:
    if hasattr(entity, "is_active"):
        entity.is_active = True
    apply_update_audit(entity, actor_id)
