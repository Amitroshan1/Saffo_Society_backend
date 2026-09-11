"""Shared list/pagination schemas."""

from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ListQueryParams(BaseModel):
    """Standard query params for list endpoints."""

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100, alias="pageSize")
    search: Optional[str] = Field(None, max_length=200)
    sort_by: str = Field("created_at", alias="sortBy")
    sort_order: Literal["asc", "desc"] = Field("desc", alias="sortOrder")
    is_active: Optional[bool] = Field(None, alias="isActive")

    model_config = {"populate_by_name": True}


class PaginationMeta(BaseModel):
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")
    has_next: bool = Field(alias="hasNext")
    has_prev: bool = Field(alias="hasPrev")

    model_config = {"populate_by_name": True}


class PaginatedResult(BaseModel, Generic[T]):
    items: List[T]
    pagination: PaginationMeta


def build_pagination_meta(page: int, page_size: int, total: int) -> Dict[str, Any]:
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
    }
