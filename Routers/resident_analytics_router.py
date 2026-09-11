"""Resident analytics portal routes — /api/v1/resident/analytics/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Services import analytics_service as svc
from Services.analytics_helpers import require_society_id
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-analytics"])

RESIDENT_ROLES = ("admin", "resident")


async def _resident_id(db: AsyncSession, user_id: UUID) -> UUID | None:
    from sqlalchemy import select
    from Models.resident import Resident

    row = (
        await db.execute(select(Resident.id).where(Resident.user_id == user_id, Resident.is_active.is_(True)))
    ).scalar_one_or_none()
    return row


@router.get("/resident/analytics/summary")
async def resident_summary(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*RESIDENT_ROLES)),
):
    society_id = require_society_id(current.society_id)
    rid = await _resident_id(db, current.user_id)
    data = await svc.get_dashboard(
        db, society_id, "resident", "summary", user_id=current.user_id, resident_id=rid
    )
    await db.commit()
    return success_response(200, "Resident analytics fetched", data)
