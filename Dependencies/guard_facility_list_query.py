"""Guard amenity booking list query dependency."""

from datetime import date
from uuid import UUID

from fastapi import Query

from Schemas.guard_facility_schema import GuardBookingListQueryParams


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_guard_booking_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("booking_date", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    amenity_id: UUID | None = Query(None, alias="amenityId"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    booking_date: date | None = Query(None, alias="date"),
) -> GuardBookingListQueryParams:
    return GuardBookingListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        status=_norm_enum(status),
        amenity_id=amenity_id,
        from_date=from_date,
        to_date=to_date,
        booking_date=booking_date,
    )
