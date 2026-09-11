"""Resident notice list query dependency."""

from fastapi import Query

from Schemas.resident_notice_schema import ResidentNoticeListQueryParams


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_resident_notice_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    unread_only: bool | None = Query(None, alias="unreadOnly"),
    view: str | None = Query(None),
) -> ResidentNoticeListQueryParams:
    return ResidentNoticeListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        category=_norm_enum(category),
        priority=_norm_enum(priority),
        unread_only=unread_only,
        view=_norm_enum(view) if view else None,
    )
