"""Mobile hub composition — thin BFF over existing domain services."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Dependencies.auth import CurrentUser
from Services.integration_helpers import DEEP_LINK_ROUTES, MOBILE_APP_CONFIG


def app_config(*, role: Optional[str] = None) -> dict[str, Any]:
    cfg = dict(MOBILE_APP_CONFIG)
    cfg["role"] = role
    return cfg


def resolve_deep_link(*, link_type: str, entity_id: Optional[str] = None) -> dict[str, Any]:
    template = DEEP_LINK_ROUTES.get(link_type)
    if not template:
        return {"resolved": False, "message": f"Unknown deep link type: {link_type}"}
    path = template.replace("{id}", entity_id or "")
    return {
        "resolved": True,
        "type": link_type,
        "path": path,
        "scheme": f"{MOBILE_APP_CONFIG['deepLinkScheme']}://{link_type}/{entity_id or ''}",
    }


async def role_home(db: AsyncSession, current: CurrentUser) -> dict[str, Any]:
    """Compose role home without reimplementing domain dashboards."""
    role = current.role
    shortcuts = []
    tiles = []

    if role == "resident":
        shortcuts = [
            {"label": "Bills", "route": "/resident/bills"},
            {"label": "Visitors", "route": "/resident/visitors"},
            {"label": "Complaints", "route": "/resident/complaints"},
            {"label": "Notices", "route": "/resident/notices"},
            {"label": "Parking", "route": "/resident/parking"},
            {"label": "Amenities", "route": "/resident/facilities"},
        ]
        tiles = [
            {"key": "outstanding", "title": "Outstanding", "hint": "Use /api/v1/resident/outstanding"},
            {"key": "notices", "title": "Notices", "hint": "Use /api/v1/resident/notices"},
            {"key": "visitors", "title": "Visitors", "hint": "Use /api/v1/resident/visitors"},
        ]
    elif role == "guard":
        shortcuts = [
            {"label": "Visitors", "route": "/guard/visitors"},
            {"label": "Parking", "route": "/guard/parking"},
            {"label": "Bookings", "route": "/guard/bookings"},
            {"label": "Alerts", "route": "/guard/notifications"},
        ]
        tiles = [
            {"key": "pending_approvals", "title": "Approvals", "hint": "Visitor approval queue"},
            {"key": "active_visitors", "title": "Active visitors", "hint": "Gate ops"},
            {"key": "offline_queue", "title": "Offline queue", "hint": "/api/mobile/v1/sync"},
        ]
    elif role == "admin":
        shortcuts = [
            {"label": "Dashboard", "route": "/admin/dashboard"},
            {"label": "Residents", "route": "/admin/residents"},
            {"label": "Complaints", "route": "/admin/complaints"},
            {"label": "Notices", "route": "/admin/notices"},
            {"label": "Analytics", "route": "/admin/analytics"},
        ]
        tiles = [
            {"key": "ops", "title": "Operations", "hint": "Compose from admin dashboards"},
        ]
    elif role == "finance":
        shortcuts = [
            {"label": "Billing", "route": "/finance/billing"},
            {"label": "Payments", "route": "/finance/payments"},
            {"label": "Reports", "route": "/finance/reports"},
        ]
        tiles = [
            {"key": "collections", "title": "Collections", "hint": "Phase 10/16 endpoints"},
        ]
    elif role in (
        "super_admin",
        "platform_support",
        "platform_auditor",
        "platform_billing",
    ):
        shortcuts = [
            {"label": "Tenants", "route": "/superadmin/tenants"},
            {"label": "Health", "route": "/superadmin/health"},
            {"label": "Integrations", "route": "/superadmin/integrations"},
        ]
        tiles = [
            {"key": "platform_health", "title": "Platform health", "hint": "/api/v1/platform/health"},
        ]
    else:
        shortcuts = []
        tiles = []

    return {
        "role": role,
        "societyId": str(current.society_id) if current.society_id else None,
        "userId": str(current.user_id),
        "shortcuts": shortcuts,
        "tiles": tiles,
        "syncEnabled": role in ("resident", "guard"),
        "message": "Mobile hub composes existing domain APIs; no duplicated business logic",
    }


def hub_capabilities(role: str) -> dict[str, Any]:
    catalog = {
        "resident": [
            "profile",
            "bills",
            "payments",
            "visitors",
            "complaints",
            "documents",
            "amenities",
            "parking",
            "notifications",
            "analytics",
        ],
        "guard": [
            "visitor_entry",
            "qr_scan",
            "vehicle_entry",
            "parking",
            "emergency_alerts",
            "offline_sync",
        ],
        "admin": [
            "dashboard",
            "residents",
            "visitors",
            "complaints",
            "documents",
            "announcements",
            "analytics",
        ],
        "finance": ["collections", "pending_bills", "reports", "payments"],
        "super_admin": [
            "tenant_monitoring",
            "health",
            "announcements",
            "platform_analytics",
            "integrations",
        ],
    }
    key = role if role in catalog else (
        "super_admin" if role.startswith("platform_") else role
    )
    return {"role": role, "capabilities": catalog.get(key, [])}
