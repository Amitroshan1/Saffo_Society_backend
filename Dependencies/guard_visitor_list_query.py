"""Guard visitor list query dependency."""

from fastapi import Query

from Schemas.guard_visitor_schema import GuardVisitorListQueryParams


def get_guard_visitor_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    purpose: str | None = Query(None),
) -> GuardVisitorListQueryParams:
    return GuardVisitorListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        status=status.strip().lower() if status else None,
        purpose=purpose.strip() if purpose else None,
    )
