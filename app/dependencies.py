from dataclasses import dataclass, field

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from auth import crud
from auth.models import Membership, User
from core.exceptions import forbidden, unauthorized
from core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class AuthContext:
    user: User
    membership: Membership | None
    society_id: int | None
    permissions: list[str] = field(default_factory=list)
    role_name: str | None = None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        sid = payload.get("sid")
    except (JWTError, KeyError, TypeError, ValueError):
        raise unauthorized()

    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise unauthorized()
    if not user.is_active:
        raise forbidden("Account is deactivated")

    membership = None
    permissions: list[str] = []
    role_name = None
    society_id = int(sid) if sid is not None else None

    if society_id is not None:
        membership = crud.get_membership(db, user.id, society_id)
        if not membership:
            raise forbidden("Not a member of this society")
        role_name = membership.role.name if membership.role else None
        permissions = [p.name for p in (membership.role.permissions or [])]
    elif user.is_platform_admin:
        from core.permissions import ALL_PERMISSIONS

        role_name = "super_admin"
        permissions = list(ALL_PERMISSIONS)
    else:
        raise forbidden("No society selected")

    return AuthContext(
        user=user,
        membership=membership,
        society_id=society_id,
        permissions=permissions,
        role_name=role_name,
    )


def require_permission(permission: str):
    def checker(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if permission not in ctx.permissions:
            raise forbidden(f"Permission denied: {permission} required")
        return ctx

    return checker

def require_resident(permission: str):
    def checker(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if ctx.role_name != "resident":
            raise forbidden("Resident role required")
        if permission not in ctx.permissions:
            raise forbidden(f"Permission denied: {permission} required")
        return ctx

    return checker