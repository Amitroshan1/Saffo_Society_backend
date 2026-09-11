"""Flat list query dependency — extends standard list params with buildingId, wingId, floorNo."""

from uuid import UUID

from fastapi import Query

from Schemas.flat import FlatListQueryParams


def get_flat_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("sequence", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    wing_id: UUID | None = Query(None, alias="wingId"),
    floor_no: str | None = Query(None, alias="floorNo", max_length=20),
) -> FlatListQueryParams:
    return FlatListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        building_id=building_id,
        wing_id=wing_id,
        floor_no=floor_no.strip() if floor_no else None,
    )
