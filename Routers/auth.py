"""Auth routes — replaces server/routes/auth.routes.js."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from Core.security import cookie_options
from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Middleware.rate_limit import limiter
from Schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterPublicRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from Services import auth_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_refresh_cookie(response: JSONResponse, token: str) -> None:
    opts = cookie_options()
    response.set_cookie(
        key=opts["key"],
        value=token,
        httponly=opts["httponly"],
        secure=opts["secure"],
        samesite=opts["samesite"],
        max_age=opts["max_age"],
        path=opts["path"],
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    opts = cookie_options()
    # Clear current + legacy variants (old path / SameSite=Lax / non-Secure).
    paths = {opts["path"], "/", "/api"}
    variants = {
        (opts["secure"], opts["samesite"]),
        (False, "lax"),
        (True, "none"),
        (False, "none"),
    }
    for path in paths:
        for secure, samesite in variants:
            response.delete_cookie(
                key=opts["key"],
                path=path,
                httponly=opts["httponly"],
                secure=secure,
                samesite=samesite,
            )


@router.post("/register")
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await auth_service.register_user(
        db,
        name=body.name,
        email=str(body.email),
        phone=body.phone,
        password=body.password,
        role=body.role.value,
        flat_id=body.flatId,
        society_id=current.society_id,
    )
    return success_response(201, "User created successfully", data)


@router.post("/login")
@limiter.limit("10/15minutes")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    data, refresh_token = await auth_service.login(
        db,
        email=str(body.email),
        password=body.password,
        role=body.role.value,
    )
    response = JSONResponse(
        status_code=200,
        content={"success": True, "message": "Login successful", "data": data},
    )
    # Drop legacy Lax /api cookies so they cannot override the new Secure cookie.
    _clear_refresh_cookie(response)
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/refresh-token")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refreshToken")
    data, new_refresh = await auth_service.refresh_tokens(db, token)
    response = JSONResponse(
        status_code=200,
        content={"success": True, "message": "Token refreshed", "data": data},
    )
    # None => concurrent refresh already rotated; keep existing cookie.
    if new_refresh:
        _set_refresh_cookie(response, new_refresh)
    return response


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refreshToken")
    await auth_service.logout(db, token)
    response = JSONResponse(
        status_code=200,
        content={"success": True, "message": "Logged out successfully", "data": {}},
    )
    _clear_refresh_cookie(response)
    return response


@router.post("/forgot-password")
@limiter.limit("10/15minutes")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    message = await auth_service.forgot_password(db, str(body.email))
    return success_response(200, message)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(
        db,
        email=str(body.email),
        otp=body.otp,
        password=body.password,
    )
    return success_response(200, "Password reset successful")


@router.post("/register-request")
@limiter.limit("10/15minutes")
async def register_request(
    request: Request,
    body: RegisterPublicRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await auth_service.register_request(
        db,
        name=body.name,
        email=str(body.email),
        phone=body.phone,
        password=body.password,
        role=body.role.value,
    )
    return success_response(201, "Account created. You can now log in.", data)
