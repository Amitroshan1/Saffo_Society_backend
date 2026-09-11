"""Guard mobile hub — thin wrapper over shared mobile hub service."""

from __future__ import annotations

from typing import Any

from Services import mobile_hub_service as hubs

GUARD_ROLE = "guard"


def hub_capabilities() -> dict[str, Any]:
    return hubs.hub_capabilities(GUARD_ROLE)
