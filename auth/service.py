from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from auth import crud
from auth.models import Membership, User
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from modules.society.models import Society


def _permissions(membership: Membership | None) -> list[str]:
    if not membership or not membership.role:
        return []
    return [p.name for p in (membership.role.permissions or [])]


def _token_payload(user: User, membership: Membership | None) -> dict:
    society_id = membership.society_id if membership else None
    role = membership.role.name if membership and membership.role else None
    if user.is_platform_admin and role is None:
        role = "super_admin"
    return {
        "access_token": create_access_token(user.id, society_id),
        "refresh_token": create_refresh_token(user.id,society_id),
        "token_type": "bearer",
        "role": role,
        "society_id": society_id,
        "permissions": _permissions(membership),
    }


def login(db: Session, email: str, password: str, society_id: int | None) -> dict:
    user = crud.get_user_by_email(db, email.strip().lower())
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    memberships = crud.get_memberships_for_user(db, user.id)

    if user.is_platform_admin and not memberships:
        return _token_payload(user, None)

    if not memberships:
        raise HTTPException(status_code=403, detail="No society membership")

    if society_id is not None:
        membership = next((m for m in memberships if m.society_id == society_id), None)
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this society")
        return _token_payload(user, membership)

    if len(memberships) == 1:
        return _token_payload(user, memberships[0])

    society_ids = [m.society_id for m in memberships]
    names = {
        row.id: row.name
        for row in db.query(Society).filter(Society.id.in_(society_ids)).all()
    }
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "society_id required",
            "societies": [
                {"id": m.society_id, "name": names.get(m.society_id, "")}
                for m in memberships
            ],
        },
    )


def refresh(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_refresh_token(refresh_token)
        user_id = int(payload["sub"])
        jti = payload["jti"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if crud.is_refresh_revoked(db, jti):
        raise HTTPException(status_code=401, detail="Refresh token has been logged out")

    user = crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    crud.revoke_refresh(db, jti, user.id, expires_at)
    sid = payload.get("sid")
    membership = None
    if sid is not None:
        membership = crud.get_membership(db, user.id, int(sid))
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this society")
    elif not user.is_platform_admin:
        raise HTTPException(status_code=401, detail="Log in again")
    return _token_payload(user, membership)

def logout(db: Session, refresh_token: str) -> dict:
    try:
        payload = decode_refresh_token(refresh_token)
        user_id = int(payload["sub"])
        jti = payload["jti"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    crud.revoke_refresh(db, jti, user_id, expires_at)
    return {"message": "Logged out"}


def switch_society(db: Session, user: User, society_id: int) -> dict:
    membership = crud.get_membership(db, user.id, society_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this society")
    return _token_payload(user, membership)