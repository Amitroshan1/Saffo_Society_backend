"""JWT and password helpers — replaces server/services/token.service.js + bcrypt usage."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from Core.config import settings

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _create_token(
    payload: Dict[str, Any],
    secret: str,
    expires_delta: timedelta,
) -> str:
    data = payload.copy()
    # jose requires JSON-serializable claims; stringify UUIDs
    for key, value in list(data.items()):
        if isinstance(value, UUID):
            data[key] = str(value)
    expire = datetime.now(timezone.utc) + expires_delta
    data["exp"] = expire
    return jwt.encode(data, secret, algorithm="HS256")


def sign_access_token(
    user_id: UUID,
    role: str,
    *,
    society_id: Optional[UUID] = None,
    extra: Optional[Dict[str, Any]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    payload: Dict[str, Any] = {"userId": str(user_id), "role": role}
    if society_id is not None:
        payload["societyId"] = str(society_id)
    if extra:
        payload.update(extra)
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return _create_token(
        payload,
        settings.JWT_SECRET,
        timedelta(minutes=minutes),
    )


def sign_refresh_token(user_id: UUID) -> str:
    return _create_token(
        {"userId": str(user_id)},
        settings.JWT_REFRESH_SECRET,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def verify_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(str(exc)) from exc


def verify_refresh_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_REFRESH_SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(str(exc)) from exc


def cookie_options() -> Dict[str, Any]:
    """Refresh cookie for SPA on another localhost port (cross-origin, same-site)."""
    return {
        "key": "refreshToken",
        "httponly": True,
        "secure": settings.is_production,
        # Lax works for credentialed XHR between localhost:5173 ↔ localhost:5000
        "samesite": "lax",
        "max_age": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        "path": "/",
    }
