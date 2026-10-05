from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_permission
from modules.resident import service
from modules.resident.schemas import (
    ChangePasswordIn,
    FlatOut,
    HouseholdMemberOut,
    ProfileOut,
    ProfileUpdate,
    GateDashboardOut
)
from core.permissions import RESIDENT_UPDATE, RESIDENT_VIEW
router = APIRouter(prefix="/resident", tags=["Resident"])


@router.get("/profile", response_model=ProfileOut)
def profile(ctx: AuthContext = Depends(require_permission(RESIDENT_VIEW)), db: Session = Depends(get_db)):
    return service.get_profile(db, ctx.user.id, ctx.society_id)


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(
    data: ProfileUpdate,
    ctx: AuthContext = Depends(require_permission(RESIDENT_UPDATE)),
    db: Session = Depends(get_db),
):
    return service.update_profile(db, ctx.user.id, ctx.society_id, data)


@router.patch("/change-password")
def change_password(
    data: ChangePasswordIn,
    ctx: AuthContext = Depends(require_permission(RESIDENT_UPDATE)),
    db: Session = Depends(get_db),
):
    return service.change_password(db, ctx.user, data.current_password, data.new_password)


@router.get("/flat", response_model=FlatOut)
def flat(ctx: AuthContext = Depends(require_permission(RESIDENT_VIEW)), db: Session = Depends(get_db)):
    return service.get_flat(db, ctx.user.id, ctx.society_id)


@router.get("/household", response_model=list[HouseholdMemberOut])
def household(ctx: AuthContext = Depends(require_permission(RESIDENT_VIEW)), db: Session = Depends(get_db)):
    return service.get_household(db, ctx.user.id, ctx.society_id)

@router.get("/gate-dashboard", response_model=GateDashboardOut)
def gate_dashboard(ctx: AuthContext = Depends(require_permission(RESIDENT_VIEW)), db: Session = Depends(get_db)):
    return service.gate_dashboard(db, ctx.user.id, ctx.society_id)