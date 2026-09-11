"""Document list query dependencies (admin/finance/guard/resident)."""

from datetime import datetime
from uuid import UUID

from fastapi import Query

from Schemas.document import (
    DocumentListQueryParams,
    FinanceDocumentListQueryParams,
)
from Dependencies.guard_document_list_query import get_guard_document_list_query
from Dependencies.resident_document_list_query import get_resident_document_list_query


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_document_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    category_id: UUID | None = Query(None, alias="categoryId"),
    scope: str | None = Query(None),
    is_pinned: bool | None = Query(None, alias="isPinned"),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
) -> DocumentListQueryParams:
    return DocumentListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        category_id=category_id,
        scope=_norm_enum(scope),
        is_pinned=is_pinned,
        from_date=from_date,
        to_date=to_date,
    )


def get_finance_document_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    category_id: UUID | None = Query(None, alias="categoryId"),
) -> FinanceDocumentListQueryParams:
    return FinanceDocumentListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        status=_norm_enum(status),
        category_id=category_id,
    )


# Guard document list query lives in Dependencies.guard_document_list_query
