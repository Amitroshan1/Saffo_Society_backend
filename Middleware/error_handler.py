"""Exception handlers — replaces server/middleware/errorHandler.js."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy.exc import IntegrityError

from Core.config import settings
from Utils.errors import ApiError
from Utils.logger import logger
from Utils.responses import error_body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.message, exc.errors),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "msg": err.get("msg"),
                    "loc": err.get("loc"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=422,
            content=error_body("Validation failed", errors),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.error("IntegrityError: %s", exc)
        message = "Resource already exists"
        orig = str(getattr(exc, "orig", exc)).lower()
        if "email" in orig:
            message = "email already exists"
        elif "phone" in orig:
            message = "phone already exists"
        return JSONResponse(status_code=409, content=error_body(message))

    @app.exception_handler(JWTError)
    async def jwt_handler(_: Request, exc: JWTError) -> JSONResponse:
        msg = str(exc).lower()
        if "expired" in msg:
            return JSONResponse(status_code=401, content=error_body("Token expired"))
        return JSONResponse(status_code=401, content=error_body("Invalid token"))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled error on %s: %s",
            request.url.path,
            exc,
            exc_info=True,
        )
        message = (
            "Internal server error"
            if settings.is_production
            else str(exc)
        )
        return JSONResponse(status_code=500, content=error_body(message))
