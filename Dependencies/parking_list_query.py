"""Parking list query dependencies (admin/finance/guard/resident)."""

from datetime import date
from uuid import UUID

from fastapi import Query

from Schemas.parking import (
    AllocationListQueryParams,
    ParkingSlotListQueryParams,
    ParkingZoneListQueryParams,
    VehicleListQueryParams,
    VisitorParkingListQueryParams,
)


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_parking_zone_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    zone_type: str | None = Query(None, alias="zoneType"),
    building_id: UUID | None = Query(None, alias="buildingId"),
) -> ParkingZoneListQueryParams:
    return ParkingZoneListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        zone_type=_norm_enum(zone_type),
        building_id=building_id,
    )


def get_parking_slot_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    zone_id: UUID | None = Query(None, alias="zoneId"),
    status: str | None = Query(None),
    slot_category: str | None = Query(None, alias="slotCategory"),
) -> ParkingSlotListQueryParams:
    return ParkingSlotListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        zone_id=zone_id,
        status=_norm_enum(status),
        slot_category=_norm_enum(slot_category),
    )


def get_vehicle_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    resident_id: UUID | None = Query(None, alias="residentId"),
    vehicle_type: str | None = Query(None, alias="vehicleType"),
    status: str | None = Query(None),
) -> VehicleListQueryParams:
    return VehicleListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        resident_id=resident_id,
        vehicle_type=_norm_enum(vehicle_type),
        status=_norm_enum(status),
    )


def get_allocation_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    resident_id: UUID | None = Query(None, alias="residentId"),
    slot_id: UUID | None = Query(None, alias="slotId"),
    vehicle_id: UUID | None = Query(None, alias="vehicleId"),
) -> AllocationListQueryParams:
    return AllocationListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        resident_id=resident_id,
        slot_id=slot_id,
        vehicle_id=vehicle_id,
    )


def get_visitor_parking_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    slot_id: UUID | None = Query(None, alias="slotId"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> VisitorParkingListQueryParams:
    return VisitorParkingListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        status=_norm_enum(status),
        slot_id=slot_id,
        from_date=from_date,
        to_date=to_date,
    )
