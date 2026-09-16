"""Auth business logic — replaces server/controllers/auth.controller.js."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import MAX_LOGIN_ATTEMPTS, OTP_EXPIRY_MINUTES
from Core.security import (
    hash_password,
    hash_token,
    sign_access_token,
    sign_refresh_token,
    verify_password,
    verify_refresh_token,
)
from Models.user import User
from Schemas.auth import AuthUserPayload
from Utils.errors import ApiError
from Utils.logger import logger

# user_id -> (token_hash, expires_epoch) — concurrent refresh / Strict Mode race
_PREVIOUS_REFRESH: Dict[UUID, Tuple[str, float]] = {}
_REFRESH_GRACE_SECONDS = 90.0


def user_payload(user: User) -> Dict[str, Any]:
    return AuthUserPayload(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        flat=user.flat_id,
        societyId=user.society_id,
        isVerified=user.is_verified,
        isActive=user.is_active,
        createdAt=user.created_at,
    ).model_dump(mode="json")


async def _find_by_email_or_phone(
    db: AsyncSession, email: str, phone: str
) -> Optional[User]:
    result = await db.execute(
        select(User).where(or_(User.email == email.lower(), User.phone == phone))
    )
    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str,
    password: str,
    role: str,
    flat_id: Optional[UUID] = None,
    society_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    email_norm = email.lower().strip()
    exists = await _find_by_email_or_phone(db, email_norm, phone)
    if exists:
        field = "Email" if exists.email == email_norm else "Phone"
        raise ApiError(409, f"{field} already registered")

    resolved_society_id = society_id
    if resolved_society_id is None:
        from Services.society_service import get_default_society

        default = await get_default_society(db)
        resolved_society_id = default.id if default else None

    user = User(
        name=name.strip(),
        email=email_norm,
        phone=phone.strip(),
        password=hash_password(password),
        password_changed_at=datetime.now(timezone.utc),
        role=role,
        flat_id=flat_id,
        society_id=resolved_society_id,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    if role == "guard" and resolved_society_id:
        from Services.staff_helpers import ensure_staff_profile_for_user

        await ensure_staff_profile_for_user(db, user.id, resolved_society_id)
    await db.commit()
    await db.refresh(user)
    return {"user": user_payload(user)}


async def register_request(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str,
    password: str,
    role: str,
) -> Dict[str, Any]:
    return await register_user(
        db,
        name=name,
        email=email,
        phone=phone,
        password=password,
        role=role,
        flat_id=None,
        society_id=None,
    )


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> Tuple[Dict[str, Any], str]:
    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(401, "Invalid credentials")

    if user.is_locked():
        lock = user.lock_until
        assert lock is not None
        if lock.tzinfo is None:
            lock = lock.replace(tzinfo=timezone.utc)
        minutes_left = ceil((lock - datetime.now(timezone.utc)).total_seconds() / 60)
        raise ApiError(423, f"Account locked. Try again in {minutes_left} minute(s)")

    if not user.is_active:
        raise ApiError(403, "Account is deactivated. Contact admin.")

    if not verify_password(password, user.password):
        user.inc_login_attempts()
        await db.commit()
        await db.refresh(user)
        if user.is_locked():
            raise ApiError(
                423, "Too many failed attempts. Account locked for 15 minutes."
            )
        remaining = MAX_LOGIN_ATTEMPTS - user.login_attempts
        raise ApiError(401, f"Invalid credentials. {remaining} attempt(s) remaining")

    user.reset_login_attempts()
    access_token = sign_access_token(user.id, user.role)
    refresh_token = sign_refresh_token(user.id)
    user.refresh_token = hash_token(refresh_token)
    await db.commit()
    await db.refresh(user)

    return (
        {"accessToken": access_token, "user": user_payload(user)},
        refresh_token,
    )


async def refresh_tokens(
    db: AsyncSession, token: Optional[str]
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Rotate access (+ refresh) using the HttpOnly refresh cookie.

    Returns ``(payload, new_refresh_or_none)``. When ``new_refresh`` is ``None``,
    a concurrent caller already rotated — mint access only and leave the cookie.
    """
    if not token:
        raise ApiError(401, "No refresh token")

    try:
        decoded = verify_refresh_token(token)
    except ValueError as exc:
        raise ApiError(401, "Invalid or expired refresh token") from exc

    hashed = hash_token(token)
    user_id = UUID(str(decoded["userId"]))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ApiError(401, "Invalid or expired refresh token")

    now = datetime.now(timezone.utc).timestamp()
    # Accept current hash, or a just-rotated previous hash (concurrent refresh /
    # React Strict Mode double-mount) within a short grace window.
    previous = _PREVIOUS_REFRESH.get(user_id)
    previous_ok = bool(
        previous and previous[0] == hashed and previous[1] > now
    )
    if user.refresh_token != hashed and not previous_ok:
        raise ApiError(401, "Invalid or expired refresh token")

    # Sibling request already rotated — issue access only; do not rotate again
    # (avoids invalidating the cookie the first response just set).
    if previous_ok and user.refresh_token != hashed:
        new_access = sign_access_token(user.id, user.role)
        return (
            {"accessToken": new_access, "user": user_payload(user)},
            None,
        )

    _PREVIOUS_REFRESH[user_id] = (hashed, now + _REFRESH_GRACE_SECONDS)

    new_access = sign_access_token(user.id, user.role)
    new_refresh = sign_refresh_token(user.id)
    user.refresh_token = hash_token(new_refresh)
    await db.commit()
    await db.refresh(user)

    return (
        {"accessToken": new_access, "user": user_payload(user)},
        new_refresh,
    )


async def logout(db: AsyncSession, token: Optional[str]) -> None:
    if token:
        hashed = hash_token(token)
        result = await db.execute(select(User).where(User.refresh_token == hashed))
        user = result.scalar_one_or_none()
        if user:
            _PREVIOUS_REFRESH.pop(user.id, None)
            user.refresh_token = None
            await db.commit()
        else:
            # Cookie may be the pre-rotation token still within grace
            try:
                decoded = verify_refresh_token(token)
                uid = UUID(str(decoded["userId"]))
                _PREVIOUS_REFRESH.pop(uid, None)
                result = await db.execute(select(User).where(User.id == uid))
                user = result.scalar_one_or_none()
                if user:
                    user.refresh_token = None
                    await db.commit()
            except ValueError:
                pass


async def forgot_password(db: AsyncSession, email: str) -> str:
    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if not user:
        return "If that email exists, OTP has been sent"

    otp = f"{secrets.randbelow(900000) + 100000}"
    user.otp = hash_password(otp)
    user.otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    await db.commit()

    from Core.config import settings

    if not settings.is_production:
        logger.info("[DEV] OTP for %s: %s", user.email, otp)

    return "OTP sent to registered email"


async def reset_password(
    db: AsyncSession, *, email: str, otp: str, password: str
) -> None:
    email_norm = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found")

    if not user.otp or not user.otp_expiry:
        raise ApiError(400, "OTP expired or not requested")

    expiry = user.otp_expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry < datetime.now(timezone.utc):
        raise ApiError(400, "OTP expired or not requested")

    if not verify_password(otp, user.otp):
        raise ApiError(400, "Invalid OTP")

    user.password = hash_password(password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.otp = None
    user.otp_expiry = None
    await db.commit()
