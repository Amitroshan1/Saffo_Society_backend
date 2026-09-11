"""Profile business logic — replaces server/controllers/profile.controller.js."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Core.security import hash_password, verify_password
from Models.user import User
from Schemas.auth import UserProfileOut
from Utils.errors import ApiError


async def get_profile(db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found.")
    return {"user": UserProfileOut.from_orm_user(user).model_dump(mode="json")}


async def update_profile(
    db: AsyncSession, user_id: UUID, updates: Dict[str, Any]
) -> Dict[str, Any]:
    if not updates:
        raise ApiError(400, "No valid fields provided for update.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found.")

    for key, value in updates.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return {"user": UserProfileOut.from_orm_user(user).model_dump(mode="json")}


async def change_password(
    db: AsyncSession,
    user_id: UUID,
    *,
    current_password: str,
    new_password: str,
) -> None:
    if not current_password or not new_password:
        raise ApiError(400, "Both currentPassword and newPassword are required.")
    if len(new_password) < 8:
        raise ApiError(400, "New password must be at least 8 characters.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found.")

    if not verify_password(current_password, user.password):
        raise ApiError(401, "Current password is incorrect.")

    if verify_password(new_password, user.password):
        raise ApiError(400, "New password must be different from the current password.")

    user.password = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()
