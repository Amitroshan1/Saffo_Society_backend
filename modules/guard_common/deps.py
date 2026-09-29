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
    if ctx.role_name != GUARD_ROLE or ctx.society_id is None:
        raise forbidden("Guard access only")
    return GuardUser(
        id=ctx.user.id,
        society_id=ctx.society_id,
        role=ctx.role_name,
        email=ctx.user.email or "",
    )


def require_guard(ctx: AuthContext = Depends(get_current_user)) -> GuardUser:
    return _to_guard(ctx)


def guard_from_token(db: Session, token: str | None) -> GuardUser:
    """WebSocket clients cannot send headers, so the token arrives as ?token=."""
    if not token:
        raise unauthorized()
    return _to_guard(get_current_user(token=token, db=db))
