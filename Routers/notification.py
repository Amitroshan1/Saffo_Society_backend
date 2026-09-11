"""Notifications & Communication routes (Phase 15)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.notification_list_query import (
    get_delivery_list_query,
    get_notification_list_query,
    get_scheduled_list_query,
    get_template_list_query,
)
from Schemas.notification import (
    BroadcastRequest,
    DeliveryListQueryParams,
    InvoiceNotificationRequest,
    NotificationListQueryParams,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    PaymentReminderRequest,
    ReceiptNotificationRequest,
    ScheduleNotificationRequest,
    ScheduledListQueryParams,
    TemplateListQueryParams,
)
from Services import (
    notification_dashboard_service,
    notification_report_service,
    notification_service,
)
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["notifications"])
ADMIN_ROLES = ("admin",)
FINANCE_ROLES = ("admin", "finance")


# ---------------------------------------------------------------------------
# Admin — templates
# ---------------------------------------------------------------------------


@router.post("/notifications/templates")
async def create_template(
    body: NotificationTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.create_template(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Notification template created", data)


@router.get("/notifications/templates")
async def list_templates(
    query: TemplateListQueryParams = Depends(get_template_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.list_templates(db, query, actor_society_id=current.society_id)
    return success_response(200, "Notification templates fetched", data)


@router.patch("/notifications/templates/{template_id}")
async def update_template(
    template_id: UUID,
    body: NotificationTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.update_template(
        db,
        template_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Notification template updated", data)


@router.delete("/notifications/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.delete_template(
        db,
        template_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Notification template disabled", data)


# ---------------------------------------------------------------------------
# Admin — broadcast / schedule / queue
# ---------------------------------------------------------------------------


@router.post("/notifications/broadcast")
async def broadcast_notification(
    body: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.broadcast(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Broadcast queued", data)


@router.post("/notifications/schedule")
async def schedule_notification(
    body: ScheduleNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.schedule_notification(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Notification scheduled", data)


@router.get("/notifications/scheduled")
async def list_scheduled(
    query: ScheduledListQueryParams = Depends(get_scheduled_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.list_scheduled(db, query, actor_society_id=current.society_id)
    return success_response(200, "Scheduled notifications fetched", data)


@router.post("/notifications/scheduled/{scheduled_id}/cancel")
async def cancel_scheduled(
    scheduled_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.cancel_scheduled(
        db,
        scheduled_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Scheduled notification cancelled", data)


@router.get("/notifications")
async def list_notifications(
    query: NotificationListQueryParams = Depends(get_notification_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.list_notifications(db, query, actor_society_id=current.society_id)
    return success_response(200, "Notifications fetched", data)


@router.get("/notifications/deliveries")
async def list_deliveries(
    query: DeliveryListQueryParams = Depends(get_delivery_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.list_deliveries(db, query, actor_society_id=current.society_id)
    return success_response(200, "Notification deliveries fetched", data)


@router.post("/notifications/retry/{delivery_id}")
async def retry_delivery(
    delivery_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.retry_delivery(
        db,
        delivery_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
    )
    return success_response(200, "Delivery retry processed", data)


@router.post("/notifications/process-due")
async def process_due_notifications(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_service.process_due(
        db, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Due notifications processed", data)


@router.get("/notifications/dashboard")
async def notifications_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
):
    data = await notification_dashboard_service.get_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Notifications dashboard fetched", data)


@router.get("/notifications/reports/{report_key}")
async def notifications_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    data = await notification_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={"from": from_date, "to": to_date},
    )
    return success_response(200, "Notification report generated", data)


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------


@router.post("/finance/notifications/payment-reminder")
async def finance_payment_reminder(
    body: PaymentReminderRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notification_service.send_payment_reminder(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Payment reminder sent", data)


@router.post("/finance/notifications/invoice")
async def finance_invoice_notification(
    body: InvoiceNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notification_service.send_invoice_notification(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Invoice notification sent", data)


@router.post("/finance/notifications/receipt")
async def finance_receipt_notification(
    body: ReceiptNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notification_service.send_receipt_notification(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Receipt notification sent", data)


@router.get("/finance/notifications/history")
async def finance_notification_history(
    query: NotificationListQueryParams = Depends(get_notification_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*FINANCE_ROLES)),
):
    data = await notification_service.list_finance_history(db, query, actor_society_id=current.society_id)
    return success_response(200, "Finance notification history fetched", data)
