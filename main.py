"""FastAPI application entry."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from Core.config import settings
from Events.notification_handlers import register_notification_handlers
from Events.analytics_handlers import register_analytics_handlers
from Events.platform_handlers import register_platform_handlers
from Events.integration_handlers import register_integration_handlers
from Database.session import init_db
from Middleware.error_handler import register_exception_handlers
from Middleware.platform_gate import PlatformGateMiddleware
from Middleware.integration_gateway import RequestIdMiddleware, IdempotencyMiddleware
from Middleware.rate_limit import limiter
from Routers import attendance as attendance_router
from Routers import facility as facility_router
from Routers import analytics as analytics_router
from Routers import auth as auth_router
from Routers import billing as billing_router
from Routers import building as building_router
from Routers import complaint as complaint_router
from Routers import document as document_router
from Routers import flat as flat_router
from Routers import gate as gate_router
from Routers import notice as notice_router
from Routers import notification as notification_router
from Routers import occupancy as occupancy_router
from Routers import parking as parking_router
from Routers import platform as platform_router
from Routers import mobile as mobile_router
from Routers import integrations as integrations_router
from Routers import profile as profile_router
from Routers import resident as resident_router
from Routers import resident_portal as resident_portal_router
from Routers import shift as shift_router
from Routers import society as society_router
from Routers import staff as staff_router
from Routers import visit as visit_router
from Routers import visitor as visitor_router
from Routers import wing as wing_router
from Routers import guard_parking_router
from Routers import guard_facility_router
from Routers import guard_document_router
from Routers import guard_notification_router
from Routers import guard_analytics_router
from Routers import guard_profile_router
from Routers import guard_mobile_router
from Routers import guard_dashboard_router
from Routers import guard_visitor_router
from Routers import resident_parking_router
from Routers import resident_facility_router
from Routers import resident_document_router
from Routers import resident_notification_router
from Routers import resident_notice_router
from Routers import resident_billing_router
from Routers import resident_analytics_router
from Routers import resident_profile_router
from Routers import resident_mobile_router
from Utils.local_upload import UPLOADS_DIR, ensure_upload_dirs
from Utils.logger import logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Society Management API")
    logger.info("Environment: %s", settings.NODE_ENV)
    await init_db()
    ensure_upload_dirs()
    register_notification_handlers()
    register_analytics_handlers()
    register_platform_handlers()
    register_integration_handlers()
    logger.info("Database ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Society Management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Too many attempts. Try again in 15 minutes.",
        },
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PlatformGateMiddleware)
register_exception_handlers(app)

cors_kwargs = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
# Credentials + wildcard origin is invalid in browsers; always use explicit origins.
origins = settings.allowed_origins
if settings.is_production:
    cors_kwargs["allow_origins"] = origins
else:
    # Dev: configured CLIENT_ORIGIN plus localhost regex for Vite ports
    cors_kwargs["allow_origins"] = origins if origins else []
    cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(auth_router.router)
app.include_router(society_router.router)
app.include_router(building_router.router)
app.include_router(wing_router.router)
app.include_router(flat_router.router)
app.include_router(resident_router.router)
app.include_router(resident_portal_router.router)
app.include_router(occupancy_router.router)
app.include_router(visitor_router.router)
app.include_router(visit_router.router)
app.include_router(complaint_router.router)
app.include_router(billing_router.router)
app.include_router(notice_router.router)
app.include_router(document_router.router)
app.include_router(facility_router.router)
app.include_router(parking_router.router)
app.include_router(notification_router.router)
app.include_router(analytics_router.router)
app.include_router(guard_parking_router.router)
app.include_router(guard_facility_router.router)
app.include_router(guard_document_router.router)
app.include_router(guard_notification_router.router)
app.include_router(guard_analytics_router.router)
app.include_router(guard_profile_router.router)
app.include_router(guard_mobile_router.router)
app.include_router(guard_dashboard_router.router)
app.include_router(guard_visitor_router.router)
app.include_router(resident_parking_router.router)
app.include_router(resident_facility_router.router)
app.include_router(resident_document_router.router)
app.include_router(resident_notification_router.router)
app.include_router(resident_notice_router.router)
app.include_router(resident_billing_router.router)
app.include_router(resident_analytics_router.router)
app.include_router(resident_profile_router.router)
app.include_router(resident_mobile_router.router)
app.include_router(platform_router.router)
app.include_router(platform_router.features_router)
app.include_router(mobile_router.router)
app.include_router(integrations_router.integrations_router)
app.include_router(integrations_router.platform_integrations_router)
app.include_router(gate_router.router)
app.include_router(staff_router.router)
app.include_router(shift_router.router)
app.include_router(attendance_router.router)

for prefix in ("/api/v1/admin", "/api/v1/finance"):
    app.include_router(profile_router.router, prefix=prefix)

ensure_upload_dirs()
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/health")
async def health():
    return {
        "success": True,
        "message": "OK",
        "service": "Society Management API",
        "status": "healthy",
    }


def run() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    run()
