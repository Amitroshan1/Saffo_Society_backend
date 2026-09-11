"""Visit list query dependency."""

from datetime import datetime
from uuid import UUID

from fastapi import Query

from Schemas.visit import VisitListQueryParams


def get_visit_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    wing_id: UUID | None = Query(None, alias="wingId"),
    flat_id: UUID | None = Query(None, alias="flatId"),
    occupancy_id: UUID | None = Query(None, alias="occupancyId"),
    visitor_id: UUID | None = Query(None, alias="visitorId"),
    status: str | None = Query(None),
    visitor_type: str | None = Query(None, alias="visitorType"),
    pass_type: str | None = Query(None, alias="passType"),
    is_preapproved: bool | None = Query(None, alias="isPreapproved"),
    from_date: datetime | None = Query(None, alias="fromDate"),
    to_date: datetime | None = Query(None, alias="toDate"),
) -> VisitListQueryParams:
    return VisitListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        building_id=building_id,
        wing_id=wing_id,
        flat_id=flat_id,
        occupancy_id=occupancy_id,
        visitor_id=visitor_id,
        status=status.strip().lower() if status else None,
        visitor_type=visitor_type.strip().lower() if visitor_type else None,
        pass_type=pass_type.strip().lower() if pass_type else None,
        is_preapproved=is_preapproved,
        from_date=from_date,
        to_date=to_date,
    )
