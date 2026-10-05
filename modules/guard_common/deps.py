from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies import AuthContext, get_current_user
from core.exceptions import forbidden, unauthorized

GUARD_ROLE = "security_guard"


@dataclass
class GuardUser:
    id: int
    society_id: int
    role: str = GUARD_ROLE
    email: str = ""


def _to_guard(ctx: AuthContext) -> GuardUser:
    if ctx.society_id is None:
        raise forbidden("No society selected")
    return GuardUser(
        id=ctx.user.id,
        society_id=ctx.society_id,
        role=ctx.role_name or "",
        email=ctx.user.email or "",
    )


def require_guard(permission: str):
    def checker(ctx: AuthContext = Depends(get_current_user)) -> GuardUser:
        user = _to_guard(ctx)
        if permission not in ctx.permissions:
            raise forbidden(f"Permission denied: {permission} required")
        return user

    return checker


def guard_from_token(db: Session, token: str | None) -> GuardUser:
    if not token:
        raise unauthorized()
    ctx = get_current_user(token=token, db=db)
    if "gate_sos:view" not in ctx.permissions:
        raise forbidden("Permission denied: gate_sos:view required")
    return _to_guard(ctx)
