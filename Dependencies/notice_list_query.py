"""Notice list query dependencies (admin + resident)."""

from datetime import datetime
from uuid import UUID

from fastapi import Query

from Schemas.notice import NoticeListQueryParams
from Dependencies.resident_notice_list_query import get_resident_notice_list_query


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_notice_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    is_pinned: bool | None = Query(None, alias="isPinned"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
) -> NoticeListQueryParams:
    return NoticeListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        category=_norm_enum(category),
        priority=_norm_enum(priority),
        is_pinned=is_pinned,
        building_id=building_id,
        from_date=from_date,
        to_date=to_date,
    )
