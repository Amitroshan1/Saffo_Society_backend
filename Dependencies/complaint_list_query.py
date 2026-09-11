"""Complaint list query dependency."""

from uuid import UUID

from fastapi import Query

from Schemas.complaint import ComplaintListQueryParams


def get_complaint_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    building_id: UUID | None = Query(None, alias="buildingId"),
    wing_id: UUID | None = Query(None, alias="wingId"),
    flat_id: UUID | None = Query(None, alias="flatId"),
    resident_id: UUID | None = Query(None, alias="residentId"),
    assigned_staff_id: UUID | None = Query(None, alias="assignedStaffId"),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    source: str | None = Query(None),
) -> ComplaintListQueryParams:
    return ComplaintListQueryParams(
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
        assigned_staff_id=assigned_staff_id,
        status=status.strip().lower().replace(" ", "_").replace("-", "_") if status else None,
        priority=priority.strip().lower() if priority else None,
        category=category.strip().lower().replace(" ", "_").replace("-", "_") if category else None,
        source=source.strip().lower() if source else None,
    )
