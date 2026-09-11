"""Resident document list query dependency."""

from uuid import UUID

from fastapi import Query

from Schemas.resident_document_schema import ResidentDocumentListQueryParams


def get_resident_document_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    category_id: UUID | None = Query(None, alias="categoryId"),
    favorites_only: bool | None = Query(None, alias="favoritesOnly"),
) -> ResidentDocumentListQueryParams:
    return ResidentDocumentListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        category_id=category_id,
        favorites_only=favorites_only,
    )
