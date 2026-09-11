"""Resident mobile hub — thin wrapper over shared mobile hub service."""

from __future__ import annotations

from typing import Any

from Services import mobile_hub_service as hubs

RESIDENT_ROLE = "resident"


def hub_capabilities() -> dict[str, Any]:
    return hubs.hub_capabilities(RESIDENT_ROLE)
