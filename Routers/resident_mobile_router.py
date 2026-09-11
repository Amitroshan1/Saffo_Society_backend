"""Resident mobile hub — /api/mobile/v1/hubs/resident."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from Dependencies.auth import CurrentUser, require_roles
from Services import resident_mobile_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/mobile/v1", tags=["resident-mobile"])


@router.get("/hubs/resident")
async def resident_hub(current: CurrentUser = Depends(require_roles("resident"))):
    return success_response(200, "OK", resident_mobile_service.hub_capabilities())
