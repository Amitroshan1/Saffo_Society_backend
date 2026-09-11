"""Analytics helpers, catalog defaults, serializers (Phase 16)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.analytics import (
    AnalyticsAccessLog,
    AnalyticsDashboardLayout,
    AnalyticsKpiDefinition,
    AnalyticsReportDefinition,
)
from Utils.errors import ApiError

ADMIN = "admin"
FINANCE = "finance"
GUARD = "guard"
RESIDENT = "resident"

ALL_STAFF_ROLES = [ADMIN, FINANCE, GUARD]
EXEC_ROLES = [ADMIN]
FIN_ROLES = [ADMIN, FINANCE]
OPS_ROLES = [ADMIN, GUARD]
RES_ROLES = [RESIDENT]


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def role_allowed(roles_json: list | None, role: str) -> bool:
    if not roles_json:
        return True
    return role in roles_json


def iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def log_access(
    db: AsyncSession,
    *,
    society_id: UUID,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_key: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AnalyticsAccessLog(
            society_id=society_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_key=resource_key,
            details_json=details or {},
        )
    )


DEFAULT_KPI_DEFS: list[dict[str, Any]] = [
    {"kpi_key": "total_residents", "name": "Total Residents", "category": "executive", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES + [FINANCE], "metric_key": "occupancy.residents.count", "sort_order": 1},
    {"kpi_key": "occupied_flats", "name": "Occupied Flats", "category": "executive", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES, "metric_key": "occupancy.flats.occupied", "sort_order": 2},
    {"kpi_key": "vacant_flats", "name": "Vacant Flats", "category": "executive", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES, "metric_key": "occupancy.flats.vacant", "sort_order": 3},
    {"kpi_key": "occupancy_rate", "name": "Occupancy Rate", "category": "executive", "unit": "percent", "formula_type": "ratio", "roles_json": EXEC_ROLES, "numerator_key": "occupancy.flats.occupied", "denominator_key": "occupancy.flats.total", "sort_order": 4},
    {"kpi_key": "monthly_revenue", "name": "Monthly Revenue", "category": "finance", "unit": "minor_currency", "formula_type": "module_adapter", "roles_json": FIN_ROLES, "metric_key": "billing.revenue.month", "sort_order": 5},
    {"kpi_key": "outstanding_bills_amount", "name": "Outstanding Bills", "category": "finance", "unit": "minor_currency", "formula_type": "module_adapter", "roles_json": FIN_ROLES, "metric_key": "billing.outstanding.amount", "sort_order": 6},
    {"kpi_key": "collection_rate", "name": "Collection Rate", "category": "finance", "unit": "percent", "formula_type": "ratio", "roles_json": FIN_ROLES, "numerator_key": "billing.collected.month", "denominator_key": "billing.billed.month", "sort_order": 7},
    {"kpi_key": "pending_complaints", "name": "Pending Complaints", "category": "operational", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES + OPS_ROLES, "metric_key": "complaint.open.count", "sort_order": 8},
    {"kpi_key": "complaint_resolution_rate", "name": "Complaint Resolution Rate", "category": "operational", "unit": "percent", "formula_type": "ratio", "roles_json": EXEC_ROLES, "numerator_key": "complaint.resolved.month", "denominator_key": "complaint.closed.month", "sort_order": 9},
    {"kpi_key": "visitor_count", "name": "Visitor Count", "category": "operational", "unit": "count", "formula_type": "module_adapter", "roles_json": OPS_ROLES + EXEC_ROLES, "metric_key": "visitor.checkins.day", "sort_order": 10},
    {"kpi_key": "parking_occupancy_rate", "name": "Parking Occupancy", "category": "operational", "unit": "percent", "formula_type": "ratio", "roles_json": OPS_ROLES + EXEC_ROLES, "numerator_key": "parking.slots.allocated", "denominator_key": "parking.slots.total", "sort_order": 11},
    {"kpi_key": "amenity_usage", "name": "Amenity Usage", "category": "operational", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES + [FINANCE], "metric_key": "amenity.bookings.day", "sort_order": 12},
    {"kpi_key": "unread_notifications", "name": "Unread Notifications", "category": "communications", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES, "metric_key": "notification.unread.count", "sort_order": 13},
    {"kpi_key": "staff_on_duty", "name": "Staff On Duty", "category": "operational", "unit": "count", "formula_type": "module_adapter", "roles_json": OPS_ROLES + EXEC_ROLES, "metric_key": "staff.on_duty.count", "sort_order": 14},
    {"kpi_key": "documents_published", "name": "Documents Published", "category": "documents", "unit": "count", "formula_type": "module_adapter", "roles_json": EXEC_ROLES + [FINANCE], "metric_key": "document.published.count", "sort_order": 15},
    {"kpi_key": "notices_read_rate", "name": "Notices Read Rate", "category": "communications", "unit": "percent", "formula_type": "ratio", "roles_json": EXEC_ROLES, "numerator_key": "notice.reads.count", "denominator_key": "notice.targets.count", "sort_order": 16},
    {"kpi_key": "overdue_amount", "name": "Overdue Amount", "category": "finance", "unit": "minor_currency", "formula_type": "module_adapter", "roles_json": FIN_ROLES, "metric_key": "billing.overdue.amount", "sort_order": 17},
    {"kpi_key": "my_outstanding", "name": "My Outstanding", "category": "resident", "unit": "minor_currency", "formula_type": "module_adapter", "roles_json": RES_ROLES, "metric_key": "resident.outstanding.amount", "sort_order": 1},
]


def _report(key, name, category, roles, strategy="live_query", charts=None, order=0):
    return {
        "report_key": key,
        "name": name,
        "category": category,
        "description": name,
        "strategy": strategy,
        "roles_json": roles,
        "columns_json": [],
        "default_filters_json": {},
        "chart_types_json": charts or ["table", "bar"],
        "sort_order": order,
    }


DEFAULT_REPORT_DEFS: list[dict[str, Any]] = [
    _report("executive.scorecard", "Executive Scorecard", "executive", EXEC_ROLES, "live_query", ["kpi_card", "table"], 1),
    _report("society.occupancy", "Society Occupancy", "society", EXEC_ROLES, "live_query", ["pie", "table"], 2),
    _report("residents.summary", "Residents Summary", "residents", EXEC_ROLES, "live_query", ["bar"], 3),
    _report("visitors.daily", "Daily Visitors", "visitors", OPS_ROLES + EXEC_ROLES, "live_query", ["bar", "heatmap"], 4),
    _report("staff.attendance", "Staff Attendance", "staff", OPS_ROLES + EXEC_ROLES, "live_query", ["table"], 5),
    _report("complaints.pipeline", "Complaints Pipeline", "complaints", EXEC_ROLES, "live_query", ["stacked_bar", "pie"], 6),
    _report("billing.outstanding", "Billing Outstanding", "billing", FIN_ROLES, "live_query", ["table", "bar"], 7),
    _report("billing.collections", "Billing Collections", "billing", FIN_ROLES, "live_query", ["line", "bar"], 8),
    _report("finance.revenue", "Finance Revenue", "finance", FIN_ROLES, "live_query", ["line", "combo"], 9),
    _report("documents.summary", "Documents Summary", "documents", EXEC_ROLES + [FINANCE], "live_query", ["pie"], 10),
    _report("amenities.utilization", "Amenity Utilization", "amenities", EXEC_ROLES + [FINANCE], "live_query", ["bar"], 11),
    _report("parking.occupancy", "Parking Occupancy", "parking", OPS_ROLES + FIN_ROLES, "live_query", ["pie", "bar"], 12),
    _report("notifications.volume", "Notification Volume", "notifications", EXEC_ROLES + [FINANCE], "live_query", ["line"], 13),
    _report("security.ops", "Security Ops", "security", OPS_ROLES + EXEC_ROLES, "live_query", ["table"], 14),
    _report("audit.access", "Analytics Access Audit", "audit", EXEC_ROLES, "live_query", ["table"], 15),
    _report("usage.portal", "Usage Analytics", "usage", EXEC_ROLES, "fact_query", ["area"], 16),
    _report("operational.today", "Operational Today Pack", "operational", OPS_ROLES + EXEC_ROLES, "live_query", ["table", "bar"], 17),
    _report("resident.billing", "My Billing Summary", "billing", RES_ROLES, "live_query", ["table"], 18),
    _report("resident.visitors", "My Visitor History", "visitors", RES_ROLES, "live_query", ["table"], 19),
    _report("resident.parking", "My Parking", "parking", RES_ROLES, "live_query", ["table"], 20),
    _report("resident.amenities", "My Amenity Bookings", "amenities", RES_ROLES, "live_query", ["table"], 21),
]

DEFAULT_LAYOUTS: list[dict[str, Any]] = [
    {
        "role": ADMIN,
        "layout_key": "executive",
        "name": "Executive Dashboard",
        "widgets_json": [
            {"type": "kpi_card", "kpiKey": "total_residents"},
            {"type": "kpi_card", "kpiKey": "occupied_flats"},
            {"type": "kpi_card", "kpiKey": "monthly_revenue"},
            {"type": "kpi_card", "kpiKey": "outstanding_bills_amount"},
            {"type": "kpi_card", "kpiKey": "pending_complaints"},
            {"type": "kpi_card", "kpiKey": "visitor_count"},
            {"type": "kpi_card", "kpiKey": "parking_occupancy_rate"},
            {"type": "kpi_card", "kpiKey": "amenity_usage"},
            {"type": "chart", "chartKey": "billing.collections", "chartType": "line"},
            {"type": "chart", "chartKey": "complaints.pipeline", "chartType": "pie"},
            {"type": "chart", "chartKey": "visitors.daily", "chartType": "bar"},
        ],
    },
    {
        "role": FINANCE,
        "layout_key": "finance",
        "name": "Finance Dashboard",
        "widgets_json": [
            {"type": "kpi_card", "kpiKey": "monthly_revenue"},
            {"type": "kpi_card", "kpiKey": "outstanding_bills_amount"},
            {"type": "kpi_card", "kpiKey": "collection_rate"},
            {"type": "kpi_card", "kpiKey": "overdue_amount"},
            {"type": "chart", "chartKey": "billing.collections", "chartType": "line"},
            {"type": "chart", "chartKey": "finance.revenue", "chartType": "bar"},
        ],
    },
    {
        "role": GUARD,
        "layout_key": "today",
        "name": "Guard Ops Today",
        "widgets_json": [
            {"type": "kpi_card", "kpiKey": "visitor_count"},
            {"type": "kpi_card", "kpiKey": "parking_occupancy_rate"},
            {"type": "kpi_card", "kpiKey": "staff_on_duty"},
            {"type": "chart", "chartKey": "operational.today", "chartType": "bar"},
        ],
    },
    {
        "role": RESIDENT,
        "layout_key": "summary",
        "name": "My Analytics",
        "widgets_json": [
            {"type": "kpi_card", "kpiKey": "my_outstanding"},
            {"type": "chart", "chartKey": "resident.billing", "chartType": "bar"},
        ],
    },
]


async def ensure_catalog_seeded(db: AsyncSession, society_id: UUID) -> None:
    existing = (
        await db.execute(
            select(AnalyticsKpiDefinition.id).where(
                AnalyticsKpiDefinition.society_id == society_id
            ).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return
    for d in DEFAULT_KPI_DEFS:
        db.add(
            AnalyticsKpiDefinition(
                society_id=society_id,
                kpi_key=d["kpi_key"],
                name=d["name"],
                category=d["category"],
                unit=d.get("unit", "count"),
                formula_type=d.get("formula_type", "direct_fact"),
                aggregation="latest",
                grain="society",
                refresh_policy="daily",
                roles_json=d.get("roles_json", []),
                metric_key=d.get("metric_key"),
                numerator_key=d.get("numerator_key"),
                denominator_key=d.get("denominator_key"),
                sort_order=d.get("sort_order", 0),
            )
        )
    for d in DEFAULT_REPORT_DEFS:
        db.add(
            AnalyticsReportDefinition(
                society_id=society_id,
                report_key=d["report_key"],
                name=d["name"],
                category=d["category"],
                description=d.get("description"),
                strategy=d.get("strategy", "live_query"),
                roles_json=d.get("roles_json", []),
                columns_json=d.get("columns_json", []),
                default_filters_json=d.get("default_filters_json", {}),
                chart_types_json=d.get("chart_types_json", []),
                sort_order=d.get("sort_order", 0),
            )
        )
    for d in DEFAULT_LAYOUTS:
        db.add(
            AnalyticsDashboardLayout(
                society_id=society_id,
                role=d["role"],
                layout_key=d["layout_key"],
                name=d["name"],
                widgets_json=d["widgets_json"],
            )
        )
    await db.flush()


def serialize_kpi_def(row: AnalyticsKpiDefinition) -> dict:
    return {
        "id": str(row.id),
        "kpiKey": row.kpi_key,
        "name": row.name,
        "category": row.category,
        "unit": row.unit,
        "formulaType": row.formula_type,
        "roles": row.roles_json or [],
        "metricKey": row.metric_key,
        "sortOrder": row.sort_order,
    }


def serialize_report_def(row: AnalyticsReportDefinition) -> dict:
    return {
        "id": str(row.id),
        "reportKey": row.report_key,
        "name": row.name,
        "category": row.category,
        "description": row.description,
        "strategy": row.strategy,
        "roles": row.roles_json or [],
        "chartTypes": row.chart_types_json or [],
        "sortOrder": row.sort_order,
    }
