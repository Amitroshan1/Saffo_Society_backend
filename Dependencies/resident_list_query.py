"""Resident list query dependency."""

from fastapi import Query

from Schemas.resident import ResidentListQueryParams


def get_resident_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("name", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
) -> ResidentListQueryParams:
    return ResidentListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
    )
