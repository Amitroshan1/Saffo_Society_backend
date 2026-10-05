from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from core.permissions import GUARD_UPDATE, GUARD_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.guard_profile.schemas import ChangePasswordIn, GuardProfileUpdate
from modules.guard_profile.service import (
    change_password,
    clear_photo,
    get_profile,
    replace_photo,
    update_profile,
)

router = APIRouter(tags=["Guard Profile"])


@router.get("/guard/profile")
def fetch_profile(
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GUARD_VIEW)),
):
    item = get_profile(db, current_user)
    return success_response("Guard profile fetched", item.model_dump(mode="json"))


@router.patch("/guard/profile")
def patch_profile(
    data: GuardProfileUpdate,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = update_profile(db, current_user, data)
    return success_response("Guard profile updated", item.model_dump(mode="json"))


@router.patch("/guard/change-password")
def patch_password(
    data: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    change_password(db, current_user, data)
    return success_response("Password updated")


@router.post("/guard/profile/photo")
def upload_profile_photo(
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GUARD_UPDATE)),
):
    item = replace_photo(db, current_user, photo)
    return success_response("Profile photo updated", item.model_dump(mode="json"))


@router.delete("/guard/profile/photo")
def delete_profile_photo(
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(GUARD_UPDATE)),
):
    item = clear_photo(db, current_user)
    return success_response("Profile photo removed", item.model_dump(mode="json"))
