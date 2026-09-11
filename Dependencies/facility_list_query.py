"""Amenity list query dependencies (admin/finance/guard/resident)."""

from datetime import date
from uuid import UUID

from fastapi import Query

from Schemas.facility import (
    FacilityListQueryParams,
    BookingListQueryParams,
)
from Dependencies.guard_facility_list_query import get_guard_booking_list_query
from Dependencies.resident_facility_list_query import get_resident_booking_list_query


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_facility_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    category: str | None = Query(None),
    is_paid: bool | None = Query(None, alias="isPaid"),
) -> FacilityListQueryParams:
    return FacilityListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        category=_norm_enum(category),
        is_paid=is_paid,
    )


def get_booking_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    facility_id: UUID | None = Query(None, alias="amenityId"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> BookingListQueryParams:
    return BookingListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        amenity_id=amenity_id,
        from_date=from_date,
        to_date=to_date,
    )

