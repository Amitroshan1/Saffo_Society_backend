"""Guard visitor portal routes — /api/v1/guard/visitors, /guard/flats."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.guard_visitor_list_query import get_guard_visitor_list_query
from Schemas.guard_visitor_schema import (
    GuardCallLogCreate,
    GuardOtpVerify,
    GuardVisitorCreate,
    GuardVisitorDecision,
    GuardVisitorListQueryParams,
)
from Services import guard_visitor_service
from Utils.errors import ApiError
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-visitors"])


async def _parse_create_payload(request: Request) -> tuple[GuardVisitorCreate, bytes | None, str | None]:
    content_type = (request.headers.get("content-type") or "").lower()
    photo_bytes: bytes | None = None
    photo_filename: str | None = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload: dict = {}
        for key, value in form.multi_items():
            if key in {"photo", "file"} and hasattr(value, "read"):
                photo_bytes = await value.read()
                photo_filename = getattr(value, "filename", None)
            else:
                payload[key] = value
        body = GuardVisitorCreate.model_validate(payload)
        return body, photo_bytes, photo_filename
    try:
        payload = await request.json()
    except Exception as exc:
        raise ApiError(422, "Invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise ApiError(422, "Invalid request body")
    return GuardVisitorCreate.model_validate(payload), None, None


@router.get("/guard/visitors/recent")
async def guard_recent_visitors(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.recent_walk_ins(
        db, actor_id=current.user_id, actor_society_id=current.society_id, limit=limit
    )
    return success_response(200, "Recent visitors fetched", data)


@router.post("/guard/visitors/photo")
async def guard_upload_visitor_photo(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    content_type = (request.headers.get("content-type") or "").lower()
    photo_bytes: bytes | None = None
    filename: str | None = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("photo") or form.get("file")
        if file is not None and hasattr(file, "read"):
            photo_bytes = await file.read()
            filename = getattr(file, "filename", None)
    else:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ApiError(422, "Photo is required")
        from Utils.local_upload import save_visitor_photo_from_payload

        url = save_visitor_photo_from_payload(
            current.society_id, payload.get("photo") or payload.get("photoUrl")
        )
        if not url:
            raise ApiError(422, "Photo is required")
        return success_response(201, "Photo uploaded", {"photoUrl": url, "photo_url": url})

    if not photo_bytes:
        raise ApiError(422, "Photo file is required")
    data = await guard_visitor_service.upload_photo(
        db,
        actor_society_id=current.society_id,
        photo_bytes=photo_bytes,
        photo_filename=filename,
    )
    return success_response(201, "Photo uploaded", data)


@router.get("/guard/visitors")
async def guard_list_visitors(
    query: GuardVisitorListQueryParams = Depends(get_guard_visitor_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.list_walk_ins(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Guard visitors fetched", data)


@router.post("/guard/visitors")
async def guard_create_visitor(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    body, photo_bytes, photo_filename = await _parse_create_payload(request)
    data = await guard_visitor_service.create_walk_in(
        db,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        photo_bytes=photo_bytes,
        photo_filename=photo_filename,
    )
    return success_response(201, "Visitor added", data)


@router.get("/guard/visitors/{visit_id}")
async def guard_get_visitor(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.get_walk_in(
        db, visit_id, actor_society_id=current.society_id
    )
    return success_response(200, "Visitor fetched", data)


@router.patch("/guard/visitors/{visit_id}/approve")
async def guard_approve_visitor(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.approve_walk_in(
        db, visit_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Visitor approved", data)


@router.patch("/guard/visitors/{visit_id}/deny")
async def guard_deny_visitor(
    visit_id: UUID,
    body: GuardVisitorDecision | None = None,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.deny_walk_in(
        db,
        visit_id,
        body or GuardVisitorDecision(),
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Visitor denied", data)


@router.patch("/guard/visitors/{visit_id}/exit")
async def guard_exit_visitor(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.exit_walk_in(
        db, visit_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Visitor exit marked", data)


@router.patch("/guard/visitors/{visit_id}/readd")
async def guard_readd_visitor(
    visit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.readd_walk_in(
        db, visit_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Visitor moved to pending", data)


@router.post("/guard/visitors/{visit_id}/verify-otp")
async def guard_verify_otp(
    visit_id: UUID,
    body: GuardOtpVerify,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.verify_otp(
        db,
        visit_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "OTP verified", data)


@router.get("/guard/flats")
async def guard_search_flats(
    q: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.search_flats(
        db, actor_society_id=current.society_id, q=q or search, limit=limit
    )
    return success_response(200, "Flats fetched", data)


@router.get("/guard/flats/{flat_id}/contact")
async def guard_flat_contact(
    flat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.flat_contact(
        db, flat_id, actor_society_id=current.society_id
    )
    return success_response(200, "Flat contact fetched", data)


@router.post("/guard/call-logs")
async def guard_call_log(
    body: GuardCallLogCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_visitor_service.log_call(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Call logged", data)
