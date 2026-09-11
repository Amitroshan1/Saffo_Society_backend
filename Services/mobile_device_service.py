"""Mobile device registration, sessions, refresh rotation, device binding."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Core.config import settings
from Core.security import hash_token, sign_access_token, sign_refresh_token, verify_password
from Models.integration import MobileDevice, MobileSession
from Models.user import User
from Services.integration_helpers import device_to_dict, emit_integration_event, utcnow
from Utils.errors import ApiError


async def register_device(
    db: AsyncSession,
    *,
    device_uid: str,
    platform: str,
    app_id: str = "resident",
    app_version: Optional[str] = None,
    os_version: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    push_token: Optional[str] = None,
    push_provider: Optional[str] = None,
    biometric_enabled: bool = False,
    user_id: Optional[UUID] = None,
    society_id: Optional[UUID] = None,
) -> MobileDevice:
    result = await db.execute(
        select(MobileDevice).where(MobileDevice.device_uid == device_uid)
    )
    device = result.scalar_one_or_none()
    if device is None:
        device = MobileDevice(
            device_uid=device_uid,
            platform=platform.lower(),
            app_id=app_id,
            app_version=app_version,
            os_version=os_version,
            fingerprint_hash=fingerprint_hash,
            push_token=push_token,
            push_provider=push_provider,
            biometric_enabled=biometric_enabled,
            user_id=user_id,
            society_id=society_id,
            status="active",
            last_seen_at=utcnow(),
        )
        db.add(device)
        await db.flush()
        emit_integration_event(
            "DeviceRegistered",
            society_id=society_id,
            entity_type="mobile_device",
            entity_id=device.id,
            actor_id=user_id,
            payload={"deviceUid": device_uid, "platform": platform, "appId": app_id},
        )
    else:
        device.platform = platform.lower()
        device.app_id = app_id
        device.app_version = app_version or device.app_version
        device.os_version = os_version or device.os_version
        if fingerprint_hash:
            device.fingerprint_hash = fingerprint_hash
        if push_token is not None:
            device.push_token = push_token
            device.push_provider = push_provider
        device.biometric_enabled = biometric_enabled
        if user_id:
            device.user_id = user_id
        if society_id:
            device.society_id = society_id
        device.status = "active"
        device.is_active = True
        device.last_seen_at = utcnow()
        await db.flush()
    return device


async def list_devices(
    db: AsyncSession,
    *,
    society_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = select(MobileDevice).where(MobileDevice.is_active.is_(True))
    if society_id:
        q = q.where(MobileDevice.society_id == society_id)
    if user_id:
        q = q.where(MobileDevice.user_id == user_id)
    q = q.order_by(MobileDevice.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [device_to_dict(r) for r in rows]


async def remove_device(
    db: AsyncSession, device_id: UUID, *, actor_id: Optional[UUID] = None
) -> dict[str, Any]:
    device = await db.get(MobileDevice, device_id)
    if not device:
        raise ApiError(404, "Device not found")
    device.status = "removed"
    device.is_active = False
    device.push_token = None
    await db.flush()
    # revoke sessions for device
    sessions = (
        await db.execute(
            select(MobileSession).where(
                MobileSession.device_id == device_id,
                MobileSession.status == "active",
            )
        )
    ).scalars().all()
    for s in sessions:
        s.status = "revoked"
        s.revoked_at = utcnow()
    emit_integration_event(
        "DeviceRemoved",
        society_id=device.society_id,
        entity_type="mobile_device",
        entity_id=device.id,
        actor_id=actor_id,
        payload={"deviceUid": device.device_uid},
    )
    return device_to_dict(device)


async def _create_session(
    db: AsyncSession,
    *,
    user: User,
    device: Optional[MobileDevice],
    family_id: Optional[UUID] = None,
    rotated_from_id: Optional[UUID] = None,
) -> tuple[str, str, MobileSession]:
    access = sign_access_token(
        user.id,
        user.role,
        society_id=user.society_id,
        extra={"deviceId": str(device.id) if device else None, "client": "mobile"},
    )
    refresh = sign_refresh_token(user.id)
    # Append device binding nonce into refresh storage only (hash of full token)
    # For device binding we store device_id on session and require matching device on refresh.
    expires = utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = MobileSession(
        user_id=user.id,
        device_id=device.id if device else None,
        society_id=user.society_id,
        refresh_token_hash=hash_token(refresh),
        family_id=family_id or uuid4(),
        rotated_from_id=rotated_from_id,
        status="active",
        expires_at=expires,
        last_used_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    return access, refresh, session


async def mobile_login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    role: Optional[str] = None,
    device_uid: str,
    platform: str,
    app_id: str = "resident",
    app_version: Optional[str] = None,
    os_version: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    biometric_enabled: bool = False,
) -> dict[str, Any]:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password):
        raise ApiError(401, "Invalid email or password")
    if not user.is_active:
        raise ApiError(403, "Account is deactivated")
    if role and user.role != role:
        raise ApiError(403, f"Role mismatch. Expected {user.role}")

    device = await register_device(
        db,
        device_uid=device_uid,
        platform=platform,
        app_id=app_id,
        app_version=app_version,
        os_version=os_version,
        fingerprint_hash=fingerprint_hash,
        biometric_enabled=biometric_enabled,
        user_id=user.id,
        society_id=user.society_id,
    )
    access, refresh, session = await _create_session(db, user=user, device=device)
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "sessionId": str(session.id),
        "device": device_to_dict(device),
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "societyId": str(user.society_id) if user.society_id else None,
        },
        "biometric": {
            "enabled": device.biometric_enabled,
            "challengeRequired": False,
            "note": "Biometrics unlock local refresh only; server auth uses refresh rotation",
        },
    }


async def refresh_mobile_session(
    db: AsyncSession,
    *,
    refresh_token: str,
    device_uid: str,
) -> dict[str, Any]:
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(MobileSession).where(
            MobileSession.refresh_token_hash == token_hash,
            MobileSession.status == "active",
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        # Possible reuse of rotated token — revoke family
        any_sess = (
            await db.execute(
                select(MobileSession).where(MobileSession.refresh_token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if any_sess:
            await _revoke_family(db, any_sess.family_id)
        raise ApiError(401, "Invalid or expired refresh token")

    if session.expires_at.replace(tzinfo=session.expires_at.tzinfo) < utcnow():
        session.status = "expired"
        raise ApiError(401, "Refresh token expired")

    device = None
    if session.device_id:
        device = await db.get(MobileDevice, session.device_id)
        if not device or device.device_uid != device_uid or device.status != "active":
            await _revoke_family(db, session.family_id)
            raise ApiError(401, "Device binding mismatch")

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise ApiError(401, "User not found or inactive")

    # rotate
    session.status = "rotated"
    session.revoked_at = utcnow()
    access, refresh, new_session = await _create_session(
        db,
        user=user,
        device=device,
        family_id=session.family_id,
        rotated_from_id=session.id,
    )
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "sessionId": str(new_session.id),
        "device": device_to_dict(device) if device else None,
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "societyId": str(user.society_id) if user.society_id else None,
        },
    }


async def logout_mobile_session(
    db: AsyncSession, *, refresh_token: Optional[str] = None, session_id: Optional[UUID] = None
) -> None:
    session = None
    if session_id:
        session = await db.get(MobileSession, session_id)
    elif refresh_token:
        session = (
            await db.execute(
                select(MobileSession).where(
                    MobileSession.refresh_token_hash == hash_token(refresh_token)
                )
            )
        ).scalar_one_or_none()
    if session:
        await _revoke_family(db, session.family_id)


async def _revoke_family(db: AsyncSession, family_id: UUID) -> None:
    rows = (
        await db.execute(
            select(MobileSession).where(
                MobileSession.family_id == family_id,
                MobileSession.status == "active",
            )
        )
    ).scalars().all()
    now = utcnow()
    for s in rows:
        s.status = "revoked"
        s.revoked_at = now


async def register_push_token(
    db: AsyncSession,
    *,
    device_uid: str,
    push_token: str,
    push_provider: str = "fcm",
    user_id: Optional[UUID] = None,
) -> dict[str, Any]:
    result = await db.execute(
        select(MobileDevice).where(MobileDevice.device_uid == device_uid)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise ApiError(404, "Device not registered")
    device.push_token = push_token
    device.push_provider = push_provider
    if user_id:
        device.user_id = user_id
    device.last_seen_at = utcnow()
    await db.flush()
    emit_integration_event(
        "PushRegistered",
        society_id=device.society_id,
        entity_type="mobile_device",
        entity_id=device.id,
        actor_id=user_id,
        payload={"provider": push_provider},
    )
    return device_to_dict(device)
