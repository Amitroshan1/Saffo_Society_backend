"""Guard mobile hub — /api/mobile/v1/hubs/guard."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from Dependencies.auth import CurrentUser, require_roles
from Services import guard_mobile_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/mobile/v1", tags=["guard-mobile"])


@router.get("/hubs/guard")
async def guard_hub(current: CurrentUser = Depends(require_roles("guard"))):
    return success_response(200, "OK", guard_mobile_service.hub_capabilities())
