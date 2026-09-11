"""Notifications & Communication business logic (Phase 15)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
    ScheduledNotification,
)
from Models.resident import Resident
from Models.staff import Staff
from Schemas.common import build_pagination_meta
from Schemas.notification import (
    BroadcastRequest,
    DeliveryListQueryParams,
    InvoiceNotificationRequest,
    NotificationListQueryParams,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    PaymentReminderRequest,
    PreferenceUpdate,
    ReceiptNotificationRequest,
    ScheduleNotificationRequest,
    ScheduledListQueryParams,
    TemplateListQueryParams,
)
from Services.notification_helpers import (
    TEMPLATE_FIELD_MAP,
    apply_fields,
    delivery_to_dict,
    enrich_variables,
    get_delivery_in_society,
    get_notification_in_society,
    get_or_create_preferences,
    get_scheduled_in_society,
    get_template_by_code,
    get_template_in_society,
    notification_to_dict,
    preference_to_dict,
    render_template,
    require_society_id,
    resolve_channels_for_user,
    resolve_recipients,
    scheduled_to_dict,
    template_to_dict,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

SIMULATED_CHANNELS = {"email", "sms", "push", "webhook"}


def _publish_notification_event(
    name: str,
    *,
    society_id: UUID,
    notification_id: UUID,
    actor_id: UUID | None = None,
    payload: Dict[str, Any] | None = None,
) -> None:
    publish_simple(
        name,
        society_id=society_id,
        entity_type="notification",
        entity_id=notification_id,
        actor_id=actor_id,
        payload=payload or {},
    )


async def _resolve_content(
    db: AsyncSession,
    society_id: UUID,
    *,
    template_id: UUID | None = None,
    template_code: str | None = None,
    title: str | None = None,
    body: str | None = None,
    variables: Dict[str, Any] | None = None,
    resident_id: UUID | None = None,
    building_id: UUID | None = None,
    wing_id: UUID | None = None,
    flat_id: UUID | None = None,
) -> tuple[str, str, NotificationTemplate | None]:
    template: NotificationTemplate | None = None
    if template_id:
        template = await get_template_in_society(db, template_id, society_id)
    elif template_code:
        template = await get_template_by_code(db, society_id, template_code)

    vars_out = await enrich_variables(
        db,
        society_id,
        variables,
        resident_id=resident_id,
        building_id=building_id,
        wing_id=wing_id,
        flat_id=flat_id,
    )

    if template:
        resolved_title = render_template(template.subject_template or template.name, vars_out)
        resolved_body = render_template(template.body_template, vars_out)
        return resolved_title, resolved_body, template

    if not title or not body:
        raise ApiError(422, "title and body are required when no template is provided")
    return render_template(title, vars_out), render_template(body, vars_out), None


async def _simulate_channel_delivery(channel: str) -> tuple[str, dict]:
    """Simulate external channel delivery (always succeeds in dev)."""
    return "delivered", {
        "simulated": True,
        "channel": channel,
        "provider": "stub",
        "messageId": f"sim-{channel}-{utcnow().timestamp()}",
    }


async def _process_delivery(
    db: AsyncSession,
    delivery: NotificationDelivery,
    notification: Notification,
    *,
    actor_id: UUID | None = None,
) -> None:
    now = utcnow()
    delivery.attempt_count += 1
    delivery.last_attempt_at = now
    delivery.status = "sending"
    apply_update_audit(delivery, actor_id or notification.created_by or notification.user_id)

    if delivery.channel == "in_app":
        delivery.status = "delivered"
        delivery.delivered_at = now
        delivery.provider_response = {"simulated": False, "channel": "in_app"}
        if notification.status in ("pending", "queued", "sending"):
            notification.status = "delivered"
            notification.sent_at = notification.sent_at or now
        _publish_notification_event(
            "NotificationDelivered",
            society_id=notification.society_id,
            notification_id=notification.id,
            actor_id=actor_id,
            payload={"deliveryId": str(delivery.id), "channel": delivery.channel},
        )
        return

    if delivery.channel in SIMULATED_CHANNELS:
        status, response = await _simulate_channel_delivery(delivery.channel)
        delivery.status = status
        delivery.provider_response = response
        if status == "delivered":
            delivery.delivered_at = now
            if notification.status in ("pending", "queued", "sending"):
                notification.status = "delivered"
                notification.sent_at = notification.sent_at or now
            _publish_notification_event(
                "NotificationDelivered",
                society_id=notification.society_id,
                notification_id=notification.id,
                actor_id=actor_id,
                payload={"deliveryId": str(delivery.id), "channel": delivery.channel},
            )
        else:
            delivery.error_message = "Simulated delivery failure"
            _publish_notification_event(
                "NotificationFailed",
                society_id=notification.society_id,
                notification_id=notification.id,
                actor_id=actor_id,
                payload={
                    "deliveryId": str(delivery.id),
                    "channel": delivery.channel,
                    "error": delivery.error_message,
                },
            )
        return

    delivery.status = "failed"
    delivery.error_message = f"Unsupported channel: {delivery.channel}"


async def _queue_deliveries(
    db: AsyncSession,
    notification: Notification,
    channels: List[str],
    recipient: Dict[str, Any],
    *,
    actor_id: UUID | None,
) -> List[NotificationDelivery]:
    deliveries: List[NotificationDelivery] = []
    prefs = None
    if recipient.get("user_id"):
        prefs = await get_or_create_preferences(
            db,
            society_id=notification.society_id,
            user_id=recipient["user_id"],
            resident_id=recipient.get("resident_id"),
            actor_id=actor_id,
        )
    allowed = resolve_channels_for_user(
        channels,
        prefs,
        category=notification.category,
        priority=notification.priority,
    )
    for channel in allowed:
        address = None
        if channel == "email":
            address = recipient.get("email")
        elif channel == "sms":
            address = recipient.get("phone")
        delivery = NotificationDelivery(
            society_id=notification.society_id,
            notification_id=notification.id,
            channel=channel,
            recipient_user_id=recipient.get("user_id"),
            recipient_resident_id=recipient.get("resident_id"),
            recipient_address=address,
            status="queued",
            attempt_count=0,
            max_attempts=3,
            provider_response={},
            metadata_json={},
        )
        db.add(delivery)
        deliveries.append(delivery)
    await db.flush()
    return deliveries


async def _create_notification_for_recipient(
    db: AsyncSession,
    *,
    society_id: UUID,
    title: str,
    body: str,
    recipient: Dict[str, Any],
    channels: List[str],
    category: str,
    priority: str,
    source_module: str,
    source_event: str | None,
    target_type: str,
    target_role: str | None,
    building_id: UUID | None,
    wing_id: UUID | None,
    flat_id: UUID | None,
    template_id: UUID | None,
    payload: Dict[str, Any],
    metadata: Dict[str, Any],
    notes: str | None,
    actor_id: UUID | None,
    scheduled_for: datetime | None = None,
) -> Notification:
    notification = Notification(
        society_id=society_id,
        template_id=template_id,
        source_module=source_module,
        source_event=source_event,
        category=category,
        priority=priority,
        title=title,
        body=body,
        payload_json=payload,
        target_type=target_type,
        target_role=target_role,
        building_id=building_id,
        wing_id=wing_id,
        flat_id=flat_id,
        resident_id=recipient.get("resident_id"),
        user_id=recipient.get("user_id"),
        status="queued" if scheduled_for else "pending",
        scheduled_for=scheduled_for,
        metadata_json=metadata,
        notes=notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(notification, actor_id or recipient.get("user_id") or society_id)
    db.add(notification)
    await db.flush()

    _publish_notification_event(
        "NotificationQueued",
        society_id=society_id,
        notification_id=notification.id,
        actor_id=actor_id,
        payload={"channels": channels, "targetType": target_type},
    )

    if not scheduled_for:
        deliveries = await _queue_deliveries(
            db, notification, channels, recipient, actor_id=actor_id
        )
        notification.status = "sending"
        for delivery in deliveries:
            await _process_delivery(db, delivery, notification, actor_id=actor_id)
        if notification.status == "delivered":
            _publish_notification_event(
                "NotificationSent",
                society_id=society_id,
                notification_id=notification.id,
                actor_id=actor_id,
            )
        elif any(d.status == "failed" for d in deliveries):
            notification.status = "failed"
    return notification


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


async def create_template(
    db: AsyncSession,
    body: NotificationTemplateCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    existing = await get_template_by_code(db, society_id, body.code)
    if existing:
        raise ApiError(409, "Template code already exists")

    template = NotificationTemplate(
        society_id=society_id,
        code=body.code,
        name=body.name,
        category=body.category,
        channel=body.channel,
        subject_template=body.subjectTemplate,
        body_template=body.bodyTemplate,
        priority=body.priority,
        is_system=body.isSystem,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(template, actor_id)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return {"template": template_to_dict(template)}


async def list_templates(
    db: AsyncSession,
    query: TemplateListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(NotificationTemplate).where(NotificationTemplate.society_id == society_id)
    if query.category:
        base = base.where(NotificationTemplate.category == query.category)
    if query.channel:
        base = base.where(NotificationTemplate.channel == query.channel)
    if query.is_active is not None:
        base = base.where(NotificationTemplate.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                NotificationTemplate.name.ilike(term),
                NotificationTemplate.code.ilike(term),
                NotificationTemplate.body_template.ilike(term),
            )
        )
    allowed_sort = ("created_at", "updated_at", "name", "code", "category", "channel")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(NotificationTemplate, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    return {
        "templates": [template_to_dict(t) for t in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def update_template(
    db: AsyncSession,
    template_id: UUID,
    body: NotificationTemplateUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    template = await get_template_in_society(db, template_id, society_id)
    if template.is_system:
        raise ApiError(403, "System templates cannot be modified")
    data = body.model_dump(exclude_unset=True)
    apply_fields(template, data, TEMPLATE_FIELD_MAP)
    apply_update_audit(template, actor_id)
    await db.commit()
    await db.refresh(template)
    return {"template": template_to_dict(template)}


async def delete_template(
    db: AsyncSession,
    template_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    template = await get_template_in_society(db, template_id, society_id)
    if template.is_system:
        raise ApiError(403, "System templates cannot be deleted")
    template.is_active = False
    apply_update_audit(template, actor_id)
    await db.commit()
    return {"template": template_to_dict(template)}


# ---------------------------------------------------------------------------
# Broadcast / schedule / lists
# ---------------------------------------------------------------------------


async def broadcast(
    db: AsyncSession,
    body: BroadcastRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    source_module: str = "system",
    source_event: str | None = "Broadcast",
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    recipients = await resolve_recipients(
        db,
        society_id,
        target_type=body.targetType,
        target_role=body.targetRole,
        building_id=body.buildingId,
        wing_id=body.wingId,
        flat_id=body.flatId,
        resident_id=body.residentId,
        user_id=body.userId,
    )
    if not recipients:
        raise ApiError(422, "No recipients matched the target")

    title, body_text, template = await _resolve_content(
        db,
        society_id,
        template_id=body.templateId,
        template_code=body.templateCode,
        title=body.title,
        body=body.body,
        variables=body.variables,
        resident_id=body.residentId,
        building_id=body.buildingId,
        wing_id=body.wingId,
        flat_id=body.flatId,
    )

    created: List[Notification] = []
    for recipient in recipients:
        notification = await _create_notification_for_recipient(
            db,
            society_id=society_id,
            title=title,
            body=body_text,
            recipient=recipient,
            channels=body.channels,
            category=body.category,
            priority=body.priority,
            source_module=source_module,
            source_event=source_event,
            target_type=body.targetType,
            target_role=body.targetRole,
            building_id=body.buildingId,
            wing_id=body.wingId,
            flat_id=body.flatId,
            template_id=template.id if template else None,
            payload=body.variables,
            metadata=body.metadata,
            notes=body.notes,
            actor_id=actor_id,
        )
        created.append(notification)

    await db.commit()
    return {
        "recipientCount": len(recipients),
        "notificationCount": len(created),
        "notifications": [notification_to_dict(n) for n in created[:20]],
    }


async def schedule_notification(
    db: AsyncSession,
    body: ScheduleNotificationRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    if body.scheduleAt <= utcnow():
        raise ApiError(422, "scheduleAt must be in the future")

    scheduled = ScheduledNotification(
        society_id=society_id,
        template_id=body.templateId,
        title=body.title,
        body=body.body,
        channels=body.channels,
        target_type=body.targetType,
        target_role=body.targetRole,
        building_id=body.buildingId,
        wing_id=body.wingId,
        flat_id=body.flatId,
        resident_ids=[str(rid) for rid in body.residentIds],
        priority=body.priority,
        category=body.category,
        schedule_at=body.scheduleAt,
        recurrence=body.recurrence or "none",
        status="scheduled",
        next_run_at=body.scheduleAt,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(scheduled, actor_id)
    db.add(scheduled)
    await db.commit()
    await db.refresh(scheduled)
    return {"scheduled": scheduled_to_dict(scheduled)}


async def list_scheduled(
    db: AsyncSession,
    query: ScheduledListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(ScheduledNotification).where(ScheduledNotification.society_id == society_id)
    if query.status:
        base = base.where(ScheduledNotification.status == query.status)
    if query.is_active is not None:
        base = base.where(ScheduledNotification.is_active == query.is_active)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(ScheduledNotification.title.ilike(term), ScheduledNotification.body.ilike(term))
        )
    sort_field = query.sort_by if query.sort_by in ("schedule_at", "created_at", "status") else "schedule_at"
    sort_col = getattr(ScheduledNotification, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    return {
        "scheduled": [scheduled_to_dict(s) for s in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def cancel_scheduled(
    db: AsyncSession,
    scheduled_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    scheduled = await get_scheduled_in_society(db, scheduled_id, society_id)
    if scheduled.status in ("completed", "cancelled"):
        raise ApiError(409, f"Scheduled notification is already {scheduled.status}")
    scheduled.status = "cancelled"
    apply_update_audit(scheduled, actor_id)
    await db.commit()
    return {"scheduled": scheduled_to_dict(scheduled)}


async def list_notifications(
    db: AsyncSession,
    query: NotificationListQueryParams,
    *,
    actor_society_id: UUID | None,
    user_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(Notification).where(
        Notification.society_id == society_id, Notification.is_active.is_(True)
    )
    if query.status:
        base = base.where(Notification.status == query.status)
    if query.category:
        base = base.where(Notification.category == query.category)
    if query.priority:
        base = base.where(Notification.priority == query.priority)
    if query.source_module:
        base = base.where(Notification.source_module == query.source_module)
    if query.user_id:
        base = base.where(Notification.user_id == query.user_id)
    elif user_id:
        base = base.where(Notification.user_id == user_id)
    if query.resident_id:
        base = base.where(Notification.resident_id == query.resident_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(Notification.title.ilike(term), Notification.body.ilike(term))
        )
    allowed_sort = ("created_at", "updated_at", "status", "priority", "scheduled_for")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Notification, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    return {
        "notifications": [notification_to_dict(n) for n in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def list_deliveries(
    db: AsyncSession,
    query: DeliveryListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(NotificationDelivery).where(NotificationDelivery.society_id == society_id)
    if query.status:
        base = base.where(NotificationDelivery.status == query.status)
    if query.channel:
        base = base.where(NotificationDelivery.channel == query.channel)
    if query.notification_id:
        base = base.where(NotificationDelivery.notification_id == query.notification_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                NotificationDelivery.recipient_address.ilike(term),
                NotificationDelivery.error_message.ilike(term),
            )
        )
    sort_field = query.sort_by if query.sort_by in ("created_at", "status", "channel") else "created_at"
    sort_col = getattr(NotificationDelivery, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    return {
        "deliveries": [delivery_to_dict(d) for d in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def retry_delivery(
    db: AsyncSession,
    delivery_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    delivery = await get_delivery_in_society(db, delivery_id, society_id)
    if delivery.status == "delivered":
        raise ApiError(409, "Delivery already completed")
    if delivery.attempt_count >= delivery.max_attempts:
        raise ApiError(422, "Maximum retry attempts exceeded")

    notification = await get_notification_in_society(db, delivery.notification_id, society_id)
    delivery.status = "queued"
    delivery.error_message = None
    await _process_delivery(db, delivery, notification, actor_id=actor_id)
    apply_update_audit(notification, actor_id)
    await db.commit()
    return {"delivery": delivery_to_dict(delivery), "notification": notification_to_dict(notification)}


def _next_recurrence(run_at: datetime, recurrence: str | None) -> datetime | None:
    if not recurrence or recurrence == "none":
        return None
    if recurrence == "daily":
        return run_at + timedelta(days=1)
    if recurrence == "weekly":
        return run_at + timedelta(weeks=1)
    if recurrence == "monthly":
        return run_at + timedelta(days=30)
    return None


async def process_due(
    db: AsyncSession,
    *,
    actor_id: UUID | None = None,
    actor_society_id: UUID | None = None,
) -> Dict[str, Any]:
    now = utcnow()
    scheduled_processed = 0
    deliveries_processed = 0

    sched_query = select(ScheduledNotification).where(
        ScheduledNotification.status == "scheduled",
        ScheduledNotification.is_active.is_(True),
        ScheduledNotification.next_run_at <= now,
    )
    if actor_society_id:
        sched_query = sched_query.where(ScheduledNotification.society_id == actor_society_id)

    due_scheduled = (await db.execute(sched_query)).scalars().all()
    for item in due_scheduled:
        item.status = "processing"
        resident_ids = [UUID(rid) for rid in (item.resident_ids or []) if rid]
        req = BroadcastRequest(
            title=item.title,
            body=item.body,
            templateId=item.template_id,
            channels=item.channels or ["in_app"],
            category=item.category,
            priority=item.priority,
            targetType=item.target_type,
            targetRole=item.target_role,
            buildingId=item.building_id,
            wingId=item.wing_id,
            flatId=item.flat_id,
            residentId=resident_ids[0] if len(resident_ids) == 1 else None,
            metadata=item.metadata_json or {},
            notes=item.notes,
        )
        if item.target_type == "resident" and len(resident_ids) > 1:
            recipients = await resolve_recipients(
                db,
                item.society_id,
                target_type="resident",
                resident_ids=resident_ids,
            )
            title, body_text, template = await _resolve_content(
                db,
                item.society_id,
                template_id=item.template_id,
                title=item.title,
                body=item.body,
            )
            for recipient in recipients:
                notification = await _create_notification_for_recipient(
                    db,
                    society_id=item.society_id,
                    title=title,
                    body=body_text,
                    recipient=recipient,
                    channels=item.channels or ["in_app"],
                    category=item.category,
                    priority=item.priority,
                    source_module="system",
                    source_event="ScheduledNotification",
                    target_type=item.target_type,
                    target_role=item.target_role,
                    building_id=item.building_id,
                    wing_id=item.wing_id,
                    flat_id=item.flat_id,
                    template_id=template.id if template else item.template_id,
                    payload={},
                    metadata=item.metadata_json or {},
                    notes=item.notes,
                    actor_id=actor_id or item.created_by,
                )
                item.created_notification_id = notification.id
        else:
            result = await broadcast(
                db,
                req,
                actor_id=actor_id or item.created_by or item.society_id,
                actor_society_id=item.society_id,
                source_module="system",
                source_event="ScheduledNotification",
            )
            if result.get("notifications"):
                item.created_notification_id = UUID(result["notifications"][0]["id"])

        item.last_run_at = now
        next_run = _next_recurrence(now, item.recurrence)
        if next_run:
            item.next_run_at = next_run
            item.status = "scheduled"
        else:
            item.status = "completed"
            item.next_run_at = None
        apply_update_audit(item, actor_id or item.created_by)
        scheduled_processed += 1

    delivery_query = select(NotificationDelivery).where(
        NotificationDelivery.status.in_(("queued", "failed")),
        NotificationDelivery.attempt_count < NotificationDelivery.max_attempts,
    )
    if actor_society_id:
        delivery_query = delivery_query.where(
            NotificationDelivery.society_id == actor_society_id
        )
    pending = (await db.execute(delivery_query.limit(200))).scalars().all()
    for delivery in pending:
        notification = await get_notification_in_society(
            db, delivery.notification_id, delivery.society_id
        )
        await _process_delivery(db, delivery, notification, actor_id=actor_id)
        deliveries_processed += 1

    await db.commit()
    return {
        "scheduledProcessed": scheduled_processed,
        "deliveriesProcessed": deliveries_processed,
        "processedAt": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Finance helpers
# ---------------------------------------------------------------------------


async def send_payment_reminder(
    db: AsyncSession,
    body: PaymentReminderRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    variables = dict(body.variables)
    if body.amount:
        variables.setdefault("amount", body.amount)
    if body.invoiceNumber:
        variables.setdefault("invoice_number", body.invoiceNumber)
    req = BroadcastRequest(
        templateCode="payment_reminder",
        title="Payment reminder",
        body="Dear {{resident_name}}, your payment of {{amount}} for invoice {{invoice_number}} is due.",
        channels=body.channels,
        category="billing",
        priority="high",
        targetType="resident",
        residentId=body.residentId,
        variables=variables,
        metadata={"billId": str(body.billId)} if body.billId else {},
    )
    return await broadcast(
        db,
        req,
        actor_id=actor_id,
        actor_society_id=actor_society_id,
        source_module="billing",
        source_event="PaymentReminder",
    )


async def send_invoice_notification(
    db: AsyncSession,
    body: InvoiceNotificationRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    variables = dict(body.variables)
    if body.amount:
        variables.setdefault("amount", body.amount)
    if body.invoiceNumber:
        variables.setdefault("invoice_number", body.invoiceNumber)
    req = BroadcastRequest(
        templateCode="invoice_issued",
        title="Invoice {{invoice_number}}",
        body="Dear {{resident_name}}, your invoice {{invoice_number}} for {{amount}} is now available.",
        channels=body.channels,
        category="billing",
        priority="normal",
        targetType="resident",
        residentId=body.residentId,
        variables=variables,
        metadata={"billId": str(body.billId)} if body.billId else {},
    )
    return await broadcast(
        db,
        req,
        actor_id=actor_id,
        actor_society_id=actor_society_id,
        source_module="billing",
        source_event="InvoiceNotification",
    )


async def send_receipt_notification(
    db: AsyncSession,
    body: ReceiptNotificationRequest,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    variables = dict(body.variables)
    if body.amount:
        variables.setdefault("amount", body.amount)
    if body.receiptNumber:
        variables.setdefault("invoice_number", body.receiptNumber)
    req = BroadcastRequest(
        templateCode="payment_received",
        title="Payment received",
        body="Thank you {{resident_name}}. We received your payment of {{amount}}.",
        channels=body.channels,
        category="billing",
        priority="normal",
        targetType="resident",
        residentId=body.residentId,
        variables=variables,
        metadata={"paymentId": str(body.paymentId)} if body.paymentId else {},
    )
    return await broadcast(
        db,
        req,
        actor_id=actor_id,
        actor_society_id=actor_society_id,
        source_module="payments",
        source_event="ReceiptNotification",
    )


async def list_finance_history(
    db: AsyncSession,
    query: NotificationListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    query = query.model_copy(update={"source_module": query.source_module or "billing"})
    data = await list_notifications(db, query, actor_society_id=actor_society_id)
    return data


# ---------------------------------------------------------------------------
# Resident / guard
# ---------------------------------------------------------------------------


async def _resolve_resident_user(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None
) -> tuple[Resident, UUID]:
    society_id = require_society_id(actor_society_id)
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")
    return resident, society_id


async def list_resident_notifications(
    db: AsyncSession,
    query: NotificationListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    _resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    return await list_notifications(
        db, query, actor_society_id=society_id, user_id=actor_id
    )


async def get_resident_notification(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    _resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    notification = await get_notification_in_society(db, notification_id, society_id)
    if notification.user_id != actor_id:
        raise ApiError(403, "Notification does not belong to this resident")
    return {"notification": notification_to_dict(notification)}


async def mark_notification_read(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    _resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    notification = await get_notification_in_society(db, notification_id, society_id)
    if notification.user_id and notification.user_id != actor_id:
        raise ApiError(403, "Notification does not belong to this user")
    now = utcnow()
    notification.read_at = now
    notification.status = "read"
    apply_update_audit(notification, actor_id)
    await db.commit()
    _publish_notification_event(
        "NotificationRead",
        society_id=society_id,
        notification_id=notification.id,
        actor_id=actor_id,
    )
    return {"notification": notification_to_dict(notification)}


async def mark_all_notifications_read(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    _resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    now = utcnow()
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.society_id == society_id,
                Notification.user_id == actor_id,
                Notification.read_at.is_(None),
                Notification.is_active.is_(True),
            )
        )
    ).scalars().all()
    for notification in rows:
        notification.read_at = now
        notification.status = "read"
        apply_update_audit(notification, actor_id)
    await db.commit()
    return {"updatedCount": len(rows)}


async def archive_notification(
    db: AsyncSession,
    notification_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    _resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    notification = await get_notification_in_society(db, notification_id, society_id)
    if notification.user_id != actor_id:
        raise ApiError(403, "Notification does not belong to this resident")
    notification.archived_at = utcnow()
    notification.status = "archived"
    apply_update_audit(notification, actor_id)
    await db.commit()
    _publish_notification_event(
        "NotificationArchived",
        society_id=society_id,
        notification_id=notification.id,
        actor_id=actor_id,
    )
    return {"notification": notification_to_dict(notification)}


async def get_preferences(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    prefs = await get_or_create_preferences(
        db,
        society_id=society_id,
        user_id=actor_id,
        resident_id=resident.id,
        actor_id=actor_id,
    )
    await db.commit()
    return {"preferences": preference_to_dict(prefs)}


async def update_preferences(
    db: AsyncSession,
    body: PreferenceUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    resident, society_id = await _resolve_resident_user(
        db, actor_id=actor_id, actor_society_id=actor_society_id
    )
    prefs = await get_or_create_preferences(
        db,
        society_id=society_id,
        user_id=actor_id,
        resident_id=resident.id,
        actor_id=actor_id,
    )
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "emailEnabled": "email_enabled",
        "smsEnabled": "sms_enabled",
        "pushEnabled": "push_enabled",
        "marketingEnabled": "marketing_enabled",
        "systemEnabled": "system_enabled",
        "emergencyEnabled": "emergency_enabled",
        "metadata": "metadata_json",
    }
    apply_fields(prefs, data, field_map)
    apply_update_audit(prefs, actor_id)
    await db.commit()
    return {"preferences": preference_to_dict(prefs)}

# ---------------------------------------------------------------------------
# Domain event processing
# ---------------------------------------------------------------------------


EVENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "ComplaintCreated": {
        "template_code": "complaint_created",
        "category": "complaint",
        "source_module": "complaints",
        "target_type": "role",
        "target_role": "admin",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "New complaint registered",
        "body": "A new complaint has been submitted and requires attention.",
    },
    "PaymentReceived": {
        "template_code": "payment_received",
        "category": "billing",
        "source_module": "payments",
        "target_from_payload": "resident",
        "channels": ["in_app", "email"],
        "priority": "normal",
        "title": "Payment received",
        "body": "Thank you {{resident_name}}. We received your payment of {{amount}}.",
    },
    "BillPublished": {
        "template_code": "invoice_issued",
        "category": "billing",
        "source_module": "billing",
        "target_from_payload": "resident",
        "channels": ["in_app", "email"],
        "priority": "normal",
        "title": "New invoice {{invoice_number}}",
        "body": "Dear {{resident_name}}, invoice {{invoice_number}} for {{amount}} is now available.",
    },
    "NoticePublished": {
        "template_code": "notice_published",
        "category": "notice",
        "source_module": "notices",
        "target_type": "society",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "New notice: {{notice_title}}",
        "body": "A new notice '{{notice_title}}' has been published for {{society_name}}.",
    },
    "DocumentCreated": {
        "template_code": "document_created",
        "category": "document",
        "source_module": "documents",
        "target_type": "society",
        "channels": ["in_app"],
        "priority": "low",
        "title": "New document available",
        "body": "Document '{{document_name}}' is now available in {{society_name}}.",
    },
    "BookingApproved": {
        "template_code": "booking_approved",
        "category": "amenity",
        "source_module": "amenities",
        "target_from_payload": "resident",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "Booking {{booking_number}} approved",
        "body": "Your amenity booking {{booking_number}} has been approved.",
    },
    "ParkingAllocated": {
        "template_code": "parking_allocated",
        "category": "parking",
        "source_module": "parking",
        "target_from_payload": "resident",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "Parking slot allocated",
        "body": "Parking slot {{parking_slot}} has been allocated to you at {{society_name}}.",
    },
    "BookingCheckedIn": {
        "template_code": "booking_checked_in",
        "category": "amenity",
        "source_module": "amenities",
        "target_from_payload": "resident",
        "channels": ["in_app"],
        "priority": "low",
        "title": "Booking checked in",
        "body": "Your amenity booking {{booking_number}} check-in is recorded.",
    },
    "VisitCheckedIn": {
        "template_code": "visitor_checked_in",
        "category": "visitor",
        "source_module": "visitors",
        "target_from_payload": "resident",
        "channels": ["in_app", "push"],
        "priority": "high",
        "title": "Visitor arrived",
        "body": "Visitor {{visitor_name}} has checked in at the gate.",
    },
    "VisitorCheckedIn": {
        "template_code": "visitor_checked_in",
        "category": "visitor",
        "source_module": "visitors",
        "target_from_payload": "resident",
        "channels": ["in_app", "push"],
        "priority": "high",
        "title": "Visitor arrived",
        "body": "Visitor {{visitor_name}} has checked in at the gate.",
    },
    "ReceiptGenerated": {
        "template_code": "payment_received",
        "category": "billing",
        "source_module": "payments",
        "target_from_payload": "resident",
        "channels": ["in_app", "email"],
        "priority": "normal",
        "title": "Receipt generated",
        "body": "Your payment receipt for {{amount}} is available.",
    },
    "ComplaintResolved": {
        "template_code": "complaint_resolved",
        "category": "complaint",
        "source_module": "complaints",
        "target_from_payload": "resident",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "Complaint resolved",
        "body": "Your complaint has been marked as resolved.",
    },
    "BillGenerated": {
        "template_code": "payment_reminder",
        "category": "billing",
        "source_module": "billing",
        "target_from_payload": "resident",
        "channels": ["in_app", "email"],
        "priority": "normal",
        "title": "Maintenance bill generated",
        "body": "Dear {{resident_name}}, a bill for {{amount}} ({{invoice_number}}) has been generated.",
    },
    "DocumentArchived": {
        "template_code": "document_archived",
        "category": "document",
        "source_module": "documents",
        "target_type": "society",
        "channels": ["in_app"],
        "priority": "low",
        "title": "Document archived",
        "body": "Document '{{document_name}}' has been archived.",
    },
    "FacilityCreated": {
        "template_code": "amenity_created",
        "category": "amenity",
        "source_module": "amenities",
        "target_type": "society",
        "channels": ["in_app"],
        "priority": "low",
        "title": "New amenity available",
        "body": "Amenity '{{amenity_name}}' is now available at {{society_name}}.",
    },
    "VehicleEntry": {
        "template_code": "visitor_checked_in",
        "category": "visitor",
        "source_module": "visitors",
        "target_type": "society",
        "channels": ["in_app"],
        "priority": "high",
        "title": "Vehicle entry recorded",
        "body": "A visitor vehicle entry was recorded at {{society_name}}.",
    },
    "SosAlertCreated": {
        "template_code": "sos_alert",
        "category": "emergency",
        "source_module": "complaints",
        "target_type": "role",
        "target_role": "guard",
        "channels": ["in_app", "push"],
        "priority": "critical",
        "title": "SOS alert",
        "body": "SOS at {{society_name}}: {{complaint_title}}. Respond from the guard dashboard.",
        "exclude_actor": True,
    },
    "GuardNoticePublished": {
        "template_code": "guard_notice",
        "category": "notice",
        "source_module": "notices",
        "target_type": "role",
        "target_role": "guard",
        "channels": ["in_app"],
        "priority": "high",
        "title": "Notice: {{notice_title}}",
        "body": "A {{priority}} {{category}} notice '{{notice_title}}' was published at {{society_name}}.",
    },
    "VisitExpected": {
        "template_code": "expected_visitor",
        "category": "visitor",
        "source_module": "visitors",
        "target_type": "role",
        "target_role": "guard",
        "channels": ["in_app"],
        "priority": "high",
        "title": "Expected visitor: {{visitor_name}}",
        "body": "{{visitor_name}} is expected at the gate for {{purpose}} at {{society_name}}.",
        "exclude_actor": True,
    },
    "SHIFT_SCHEDULED": {
        "template_code": "shift_scheduled",
        "category": "system",
        "source_module": "staff",
        "target_from_payload": "staff",
        "channels": ["in_app"],
        "priority": "normal",
        "title": "Shift scheduled",
        "body": "Your {{shift_type}} shift is scheduled for {{shift_date}} at {{society_name}}.",
    },
    "ComplaintAssigned": {
        "template_code": "complaint_assigned",
        "category": "complaint",
        "source_module": "complaints",
        "target_from_payload": "staff",
        "channels": ["in_app"],
        "priority": "high",
        "title": "Complaint assigned to you",
        "body": "Complaint '{{complaint_title}}' has been assigned to you at {{society_name}}.",
    },
}


async def process_domain_event(db: AsyncSession, event_name: str, event_payload: Dict[str, Any]) -> None:
    """Create notifications from a domain event (called by event handlers)."""
    config = EVENT_CONFIG.get(event_name)
    if not config:
        return

    society_id = event_payload.get("society_id")
    if not society_id:
        return
    if isinstance(society_id, str):
        society_id = UUID(society_id)

    target_type = config.get("target_type", "resident")
    target_role = config.get("target_role")
    resident_id = None
    user_id = None

    raw_variables = dict(event_payload.get("payload") or {})
    if config.get("target_from_payload") == "resident":
        rid = raw_variables.get("residentId")
        if rid:
            resident_id = UUID(rid) if isinstance(rid, str) else rid
            target_type = "resident"
    elif config.get("target_from_payload") == "staff":
        sid = raw_variables.get("staffId") or raw_variables.get("assignedStaffId")
        if not sid:
            return
        staff_uuid = UUID(sid) if isinstance(sid, str) else sid
        staff = (
            await db.execute(
                select(Staff).where(Staff.id == staff_uuid, Staff.society_id == society_id)
            )
        ).scalar_one_or_none()
        if not staff or not staff.user_id:
            return
        user_id = staff.user_id
        target_type = "user"

    variables = await enrich_variables(
        db, society_id, raw_variables, resident_id=resident_id
    )

    title = config.get("title")
    body = config.get("body")
    template_code = config.get("template_code")

    template = await get_template_by_code(db, society_id, template_code) if template_code else None
    if template:
        resolved_title = render_template(template.subject_template or template.name, variables)
        resolved_body = render_template(template.body_template, variables)
    else:
        resolved_title = render_template(title or f"Notification: {event_name}", variables)
        resolved_body = render_template(body or "You have a new update.", variables)

    recipients = await resolve_recipients(
        db,
        society_id,
        target_type=target_type,
        target_role=target_role,
        resident_id=resident_id,
        user_id=user_id,
    )
    actor_id = event_payload.get("actor_id")
    if config.get("exclude_actor") and actor_id:
        actor_key = str(actor_id)
        recipients = [r for r in recipients if str(r.get("user_id") or "") != actor_key]
    if not recipients:
        return

    for recipient in recipients:
        await _create_notification_for_recipient(
            db,
            society_id=society_id,
            title=resolved_title,
            body=resolved_body,
            recipient=recipient,
            channels=config.get("channels", ["in_app"]),
            category=config.get("category", "system"),
            priority=config.get("priority", "normal"),
            source_module=config.get("source_module", "system"),
            source_event=event_name,
            target_type=target_type,
            target_role=target_role,
            building_id=None,
            wing_id=None,
            flat_id=None,
            template_id=template.id if template else None,
            payload=variables,
            metadata={"event": event_name},
            notes=None,
            actor_id=actor_id,
        )
    await db.commit()
