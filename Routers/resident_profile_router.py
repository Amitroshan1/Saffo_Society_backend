"""Resident profile routes — /api/v1/resident/profile."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Schemas.auth import ChangePasswordRequest, ProfileUpdateRequest
from Services import resident_profile_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/resident", tags=["resident-profile"])


@router.get("/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_profile_service.get_profile(db, current.user_id)
    return success_response(200, "Profile fetched successfully.", data)


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    updates = body.to_orm_updates()
    data = await resident_profile_service.update_profile(db, current.user_id, updates)
    return success_response(200, "Profile updated successfully.", data)


@router.patch("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    await resident_profile_service.change_password(
        db,
        current.user_id,
        current_password=body.currentPassword,
        new_password=body.newPassword,
    )
    return success_response(200, "Password changed successfully.")
