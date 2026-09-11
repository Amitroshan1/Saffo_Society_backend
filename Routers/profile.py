"""Profile routes — replaces server/routes/user.routes.js (mounted per role)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Dependencies.auth import CurrentUser, get_current_user
from Database.session import get_db
from Schemas.auth import ChangePasswordRequest, ProfileUpdateRequest
from Services import profile_service
from Utils.responses import success_response

router = APIRouter(tags=["profile"])


@router.get("/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await profile_service.get_profile(db, current.user_id)
    return success_response(200, "Profile fetched successfully.", data)


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    updates = body.to_orm_updates()
    data = await profile_service.update_profile(db, current.user_id, updates)
    return success_response(200, "Profile updated successfully.", data)


@router.patch("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    await profile_service.change_password(
        db,
        current.user_id,
        current_password=body.currentPassword,
        new_password=body.newPassword,
    )
    return success_response(200, "Password changed successfully.")
