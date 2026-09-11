"""Request ID + lightweight idempotency for mobile/integration surfaces."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from Database.session import AsyncSessionLocal
from Models.integration import IdempotencyKey
from Services.integration_helpers import utcnow
from sqlalchemy import select


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Applies to unsafe methods on /api/mobile and /api/integrations when Idempotency-Key set."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not (
            path.startswith("/api/mobile/") or path.startswith("/api/integrations/")
        ):
            return await call_next(request)
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        key = request.headers.get("idempotency-key") or request.headers.get(
            "Idempotency-Key"
        )
        if not key:
            return await call_next(request)

        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive)

        user_hint = request.headers.get("authorization", "")[:32]
        device_hint = request.headers.get("x-device-id", "")
        scope = f"{path}:{user_hint}:{device_hint}"
        req_hash = hashlib.sha256(body or b"").hexdigest()

        async with AsyncSessionLocal() as db:
            existing = (
                await db.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.scope_key == scope,
                        IdempotencyKey.idempotency_key == key,
                    )
                )
            ).scalar_one_or_none()
            if existing and existing.expires_at > utcnow():
                if existing.request_hash != req_hash:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "success": False,
                            "message": "Idempotency key reuse with different payload",
                        },
                    )
                if existing.response_json is not None:
                    return JSONResponse(
                        status_code=existing.status_code or 200,
                        content=existing.response_json,
                        headers={"X-Idempotent-Replay": "1"},
                    )

        response = await call_next(request)

        # Only cache JSON success-ish responses
        if response.status_code < 500 and hasattr(response, "body_iterator"):
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            raw = b"".join(chunks)
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else None
            except Exception:
                payload = None
            if payload is not None:
                async with AsyncSessionLocal() as db:
                    db.add(
                        IdempotencyKey(
                            scope_key=scope,
                            idempotency_key=key,
                            request_hash=req_hash,
                            response_json=payload,
                            status_code=response.status_code,
                            expires_at=utcnow() + timedelta(hours=48),
                        )
                    )
                    await db.commit()
            return Response(
                content=raw,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        return response
