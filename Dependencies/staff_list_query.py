"""Staff list query dependency."""

from uuid import UUID

from fastapi import Query

from Schemas.staff import StaffListQueryParams


def get_staff_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("name", alias="sortBy"),
    sort_order: str = Query("asc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    staff_role: str | None = Query(None, alias="staffRole"),
    employment_type: str | None = Query(None, alias="employmentType"),
    assigned_gate_id: UUID | None = Query(None, alias="assignedGateId"),
    assigned_building_id: UUID | None = Query(None, alias="assignedBuildingId"),
) -> StaffListQueryParams:
    return StaffListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        staff_role=staff_role.strip().lower() if staff_role else None,
        employment_type=employment_type.strip().lower() if employment_type else None,
        assigned_gate_id=assigned_gate_id,
        assigned_building_id=assigned_building_id,
    )
