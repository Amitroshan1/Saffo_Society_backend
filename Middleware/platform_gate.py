"""Tenant suspension + maintenance + feature gate middleware."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from Constants.constants import PLATFORM_ROLES
from Core.security import verify_access_token
from Database.session import AsyncSessionLocal
from Services.platform_helpers import FEATURE_PATH_PREFIXES
from Utils.logger import logger


def _is_exempt(path: str) -> bool:
    if path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return True
    if path.startswith("/api/v1/auth"):
        return True
    if path.startswith("/api/v1/platform"):
        return True
    if path.startswith("/uploads"):
        return True
    return False


class PlatformGateMiddleware(BaseHTTPMiddleware):
    """Blocks suspended tenants and maintenance mode for society APIs."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or _is_exempt(path):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return await call_next(request)

        token = auth.split(" ", 1)[1].strip()
        try:
            decoded = verify_access_token(token)
        except Exception:
            return await call_next(request)

        role = decoded.get("role") or ""
        if role in PLATFORM_ROLES:
            return await call_next(request)

        society_raw = decoded.get("societyId")
        # Fallback: load society from DB user if claim absent — skip heavy path; status check needs society
        try:
            async with AsyncSessionLocal() as db:
                from Services.platform_settings_service import get_maintenance
                from Services.platform_tenant_service import (
                    get_tenant_status_for_society,
                    resolve_tenant_by_society,
                )
                from Services.platform_feature_service import is_feature_enabled
                from Models.user import User
                from sqlalchemy import select

                maintenance = await get_maintenance(db)
                if maintenance.get("enabled"):
                    return JSONResponse(
                        status_code=503,
                        content={
                            "success": False,
                            "message": maintenance.get("message")
                            or "Platform under maintenance",
                            "data": {"maintenance": True},
                        },
                    )

                society_id = None
                if society_raw:
                    society_id = UUID(str(society_raw))
                else:
                    uid = decoded.get("userId")
                    if uid:
                        user = (
                            await db.execute(select(User).where(User.id == UUID(str(uid))))
                        ).scalar_one_or_none()
                        if user:
                            society_id = user.society_id

                if society_id:
                    status = await get_tenant_status_for_society(db, society_id)
                    if status and status not in ("active", None):
                        if status == "suspended":
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "success": False,
                                    "message": "Tenant suspended",
                                    "data": {"code": "TENANT_SUSPENDED"},
                                },
                            )
                        if status in ("archived", "pending_delete", "draft", "provisioning"):
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "success": False,
                                    "message": f"Tenant not available ({status})",
                                    "data": {"code": "TENANT_INACTIVE"},
                                },
                            )

                    # Feature gate by path
                    for prefix, flag_key in FEATURE_PATH_PREFIXES:
                        if path.startswith(prefix):
                            enabled = await is_feature_enabled(db, society_id, flag_key)
                            if not enabled:
                                return JSONResponse(
                                    status_code=403,
                                    content={
                                        "success": False,
                                        "message": f"Feature disabled: {flag_key}",
                                        "data": {"code": "FEATURE_DISABLED", "flag": flag_key},
                                    },
                                )
                            break
        except Exception:
            logger.exception("platform_gate_middleware_failed")

        return await call_next(request)
