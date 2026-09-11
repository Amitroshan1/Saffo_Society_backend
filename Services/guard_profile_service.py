"""Guard profile — thin wrapper over shared profile service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Services import profile_service


async def get_profile(db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    return await profile_service.get_profile(db, user_id)


async def update_profile(
    db: AsyncSession, user_id: UUID, updates: Dict[str, Any]
) -> Dict[str, Any]:
    return await profile_service.update_profile(db, user_id, updates)


async def change_password(
    db: AsyncSession,
    user_id: UUID,
    *,
    current_password: str,
    new_password: str,
) -> None:
    await profile_service.change_password(
        db,
        user_id,
        current_password=current_password,
        new_password=new_password,
    )
