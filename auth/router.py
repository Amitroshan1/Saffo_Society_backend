from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, get_current_user, require_permission
from auth import service
from auth.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SwitchSocietyRequest,
    TokenResponse,
)
from core.permissions import USERS_VIEW

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return service.login(db, data.email, data.password, data.society_id)

@router.post("/logout")
def logout(data: RefreshRequest, db: Session = Depends(get_db)):
    return service.logout(db, data.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return service.refresh(db, data.refresh_token)


@router.post("/switch-society", response_model=TokenResponse)
def switch_society(
    data: SwitchSocietyRequest,
    ctx: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.switch_society(db, ctx.user, data.society_id)


@router.get("/me", response_model=MeResponse)
def me(ctx: AuthContext = Depends(get_current_user)):
    return MeResponse(
        user_id=ctx.user.id,
        email=ctx.user.email,
        is_platform_admin=ctx.user.is_platform_admin,
        role=ctx.role_name,
        society_id=ctx.society_id,
        permissions=ctx.permissions,
    )


@router.get("/admin-ping")
def admin_ping(_: AuthContext = Depends(require_permission(USERS_VIEW))):
    return {"ok": True}