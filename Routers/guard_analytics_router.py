"""Guard analytics portal routes — /api/v1/guard/analytics/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Services import analytics_service as svc
from Services.analytics_helpers import require_society_id
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-analytics"])

GUARD_ROLES = ("admin", "guard")


@router.get("/guard/analytics/today")
async def guard_today(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*GUARD_ROLES)),
):
    society_id = require_society_id(current.society_id)
    data = await svc.get_dashboard(db, society_id, "guard", "today", user_id=current.user_id)
    await db.commit()
    return success_response(200, "Guard analytics fetched", data)
