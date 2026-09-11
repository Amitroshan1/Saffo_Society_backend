"""Occupancy list query dependency."""

from uuid import UUID

from fastapi import Query

from Schemas.occupancy import OccupancyListQueryParams


def get_occupancy_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("move_in_date", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    wing_id: UUID | None = Query(None, alias="wingId"),
    flat_id: UUID | None = Query(None, alias="flatId"),
    resident_id: UUID | None = Query(None, alias="residentId"),
    role: str | None = Query(None),
    status: str | None = Query(None),
    is_primary: bool | None = Query(None, alias="isPrimary"),
    current_only: bool | None = Query(None, alias="currentOnly"),
) -> OccupancyListQueryParams:
    return OccupancyListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        building_id=building_id,
        wing_id=wing_id,
        flat_id=flat_id,
        resident_id=resident_id,
        role=role.strip().lower() if role else None,
        status=status.strip().lower() if status else None,
        is_primary=is_primary,
        current_only=current_only,
    )
