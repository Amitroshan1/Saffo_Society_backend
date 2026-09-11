"""Mobile API BFF — /api/mobile/v1/*"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from Dependencies.auth import CurrentUser, get_current_user, require_roles
from Database.session import get_db
from Schemas.integration import (
    CrashReportRequest,
    DeepLinkResolveRequest,
    DeviceRegisterRequest,
    MediaUploadRequest,
    MobileLoginRequest,
    MobileLogoutRequest,
    MobileRefreshRequest,
    PaymentIntentCreate,
    PushRegisterRequest,
    SyncPullRequest,
    SyncPushRequest,
)
from Services import mobile_device_service as devices
from Services import mobile_hub_service as hubs
from Services import payment_orchestrator_service as payments
from Services import sync_service as sync
from Services.integration_admin_service import ingest_crash_report, mint_download_url, mint_upload_token
from Utils.responses import success_response

router = APIRouter(prefix="/api/mobile/v1", tags=["Mobile API"])


@router.get("/app/config")
async def get_app_config(current: CurrentUser = Depends(get_current_user)):
    return success_response(200, "OK", hubs.app_config(role=current.role))


@router.get("/app/config/public")
async def get_public_app_config():
    return success_response(200, "OK", hubs.app_config())


@router.post("/auth/login")
async def mobile_login(body: MobileLoginRequest, db: AsyncSession = Depends(get_db)):
    data = await devices.mobile_login(
        db,
        email=body.email,
        password=body.password,
        role=body.role,
        device_uid=body.deviceUid,
        platform=body.platform,
        app_id=body.appId,
        app_version=body.appVersion,
        os_version=body.osVersion,
        fingerprint_hash=body.fingerprintHash,
        biometric_enabled=body.biometricEnabled,
    )
    await db.commit()
    return success_response(200, "Logged in", data)


@router.post("/auth/refresh")
async def mobile_refresh(body: MobileRefreshRequest, db: AsyncSession = Depends(get_db)):
    data = await devices.refresh_mobile_session(
        db, refresh_token=body.refreshToken, device_uid=body.deviceUid
    )
    await db.commit()
    return success_response(200, "Token refreshed", data)


@router.post("/auth/logout")
async def mobile_logout(body: MobileLogoutRequest, db: AsyncSession = Depends(get_db)):
    await devices.logout_mobile_session(
        db, refresh_token=body.refreshToken, session_id=body.sessionId
    )
    await db.commit()
    return success_response(200, "Logged out", {})


@router.post("/devices/register")
async def register_device(
    body: DeviceRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    device = await devices.register_device(
        db,
        device_uid=body.deviceUid,
        platform=body.platform,
        app_id=body.appId,
        app_version=body.appVersion,
        os_version=body.osVersion,
        fingerprint_hash=body.fingerprintHash,
        push_token=body.pushToken,
        push_provider=body.pushProvider,
        biometric_enabled=body.biometricEnabled,
        user_id=current.user_id,
        society_id=current.society_id,
    )
    await db.commit()
    from Services.integration_helpers import device_to_dict

    return success_response(200, "Device registered", device_to_dict(device))


@router.get("/devices/me")
async def my_devices(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    rows = await devices.list_devices(db, user_id=current.user_id)
    return success_response(200, "OK", {"devices": rows})


@router.post("/push/register")
async def push_register(
    body: PushRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await devices.register_push_token(
        db,
        device_uid=body.deviceUid,
        push_token=body.pushToken,
        push_provider=body.pushProvider,
        user_id=current.user_id,
    )
    await db.commit()
    return success_response(200, "Push registered", data)


@router.get("/home")
async def mobile_home(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await hubs.role_home(db, current)
    return success_response(200, "OK", data)


@router.get("/hubs/{role}")
async def role_hub(role: str, current: CurrentUser = Depends(get_current_user)):
    if current.role != role and not (
        role == "super_admin" and current.role.startswith("platform_")
    ):
        # Still return capability catalog for same-family platform roles
        if role != current.role:
            pass
    return success_response(200, "OK", hubs.hub_capabilities(current.role))


@router.get("/hubs/admin")
async def admin_hub(current: CurrentUser = Depends(require_roles("admin"))):
    return success_response(200, "OK", hubs.hub_capabilities("admin"))


@router.get("/hubs/finance")
async def finance_hub(current: CurrentUser = Depends(require_roles("finance"))):
    return success_response(200, "OK", hubs.hub_capabilities("finance"))


@router.get("/hubs/superadmin")
async def superadmin_hub(
    current: CurrentUser = Depends(
        require_roles(
            "super_admin", "platform_support", "platform_auditor", "platform_billing"
        )
    ),
):
    return success_response(200, "OK", hubs.hub_capabilities(current.role))


@router.post("/sync/pull")
async def sync_pull(
    body: SyncPullRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
):
    device_uuid = UUID(x_device_id) if x_device_id else None
    data = await sync.sync_pull(
        db,
        user_id=current.user_id,
        device_id=device_uuid,
        society_id=current.society_id,
        cursor=body.cursor,
        collections=body.collections,
    )
    await db.commit()
    return success_response(200, "OK", data)


@router.post("/sync/push")
async def sync_push(
    body: SyncPushRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
):
    device_uuid = UUID(x_device_id) if x_device_id else None
    data = await sync.sync_push(
        db,
        user_id=current.user_id,
        device_id=device_uuid,
        society_id=current.society_id,
        mutations=body.mutations,
    )
    await db.commit()
    return success_response(200, "OK", data)


@router.get("/sync/status")
async def sync_status(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
    x_device_id: Optional[str] = Header(default=None, alias="X-Device-Id"),
):
    device_uuid = UUID(x_device_id) if x_device_id else None
    data = await sync.sync_status(db, user_id=current.user_id, device_id=device_uuid)
    return success_response(200, "OK", data)


@router.post("/deeplink/resolve")
async def deeplink_resolve(
    body: DeepLinkResolveRequest,
    current: CurrentUser = Depends(get_current_user),
):
    data = hubs.resolve_deep_link(link_type=body.type, entity_id=body.id or body.code)
    return success_response(200, "OK", data)


@router.post("/media/upload-token")
async def media_upload_token(
    body: MediaUploadRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await mint_upload_token(
        db,
        society_id=current.society_id,
        user_id=current.user_id,
        module=body.module,
        filename=body.filename,
        content_type=body.contentType,
        provider_code=body.providerCode,
    )
    await db.commit()
    return success_response(200, "Upload token minted", data)


@router.get("/media/{storage_object_id}/download")
async def media_download(
    storage_object_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await mint_download_url(
        db, storage_object_id=storage_object_id, user_id=current.user_id
    )
    await db.commit()
    return success_response(200, "OK", data)


@router.post("/payments/intents")
async def create_intent(
    body: PaymentIntentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident", "finance", "admin")),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    if not current.society_id:
        from Utils.errors import ApiError

        raise ApiError(400, "Society context required")
    data = await payments.create_payment_intent(
        db,
        society_id=current.society_id,
        user_id=current.user_id,
        bill_id=body.billId,
        provider_code=body.providerCode,
        idempotency_key=body.idempotencyKey or idempotency_key,
    )
    await db.commit()
    return success_response(200, "Payment intent created", data)


@router.post("/crash-reports")
async def crash_reports(
    body: CrashReportRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    data = await ingest_crash_report(
        db,
        message=body.message,
        society_id=current.society_id,
        user_id=current.user_id,
        device_id=body.deviceId,
        app_id=body.appId,
        app_version=body.appVersion,
        platform=body.platform,
        stack_hash=body.stackHash,
        breadcrumbs=body.breadcrumbs,
    )
    await db.commit()
    return success_response(200, "Accepted", data)


@router.get("/health")
async def mobile_health(request: Request):
    return success_response(200, "OK",
        {
            "surface": "mobile",
            "requestId": getattr(request.state, "request_id", None),
        },
    )
