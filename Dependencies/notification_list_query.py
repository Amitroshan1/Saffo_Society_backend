"""Notification list query dependencies."""

from uuid import UUID

from fastapi import Query

from Schemas.notification import (
    DeliveryListQueryParams,
    NotificationListQueryParams,
    ScheduledListQueryParams,
    TemplateListQueryParams,
)


def _norm_enum(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_template_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    category: str | None = Query(None),
    channel: str | None = Query(None),
) -> TemplateListQueryParams:
    return TemplateListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        category=_norm_enum(category),
        channel=_norm_enum(channel),
    )


def get_notification_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    source_module: str | None = Query(None, alias="sourceModule"),
    user_id: UUID | None = Query(None, alias="userId"),
    resident_id: UUID | None = Query(None, alias="residentId"),
) -> NotificationListQueryParams:
    return NotificationListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
        category=_norm_enum(category),
        priority=_norm_enum(priority),
        source_module=_norm_enum(source_module),
        user_id=user_id,
        resident_id=resident_id,
    )


def get_delivery_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("created_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    notification_id: UUID | None = Query(None, alias="notificationId"),
) -> DeliveryListQueryParams:
    return DeliveryListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        status=_norm_enum(status),
        channel=_norm_enum(channel),
        notification_id=notification_id,
    )


def get_scheduled_list_query(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    sort_by: str = Query("schedule_at", alias="sortBy"),
    sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
    is_active: bool | None = Query(None, alias="isActive"),
    status: str | None = Query(None),
) -> ScheduledListQueryParams:
    return ScheduledListQueryParams(
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        sort_by=sort_by,
        sort_order=sort_order,  # type: ignore[arg-type]
        is_active=is_active,
        status=_norm_enum(status),
    )
