"""Notification dashboard KPIs (Phase 15)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.notification import (
    Notification,
    NotificationDelivery,
    NotificationTemplate,
    ScheduledNotification,
)
from Services.notification_helpers import notification_to_dict, require_society_id


async def get_dashboard(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def _count_notifications(*clauses) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(
                        Notification.society_id == society_id,
                        Notification.is_active.is_(True),
                        *clauses,
                    )
                )
            ).scalar_one()
        )

    total = await _count_notifications()
    queued = await _count_notifications(Notification.status.in_(("pending", "queued", "sending")))
    delivered = await _count_notifications(Notification.status == "delivered")
    failed = await _count_notifications(Notification.status == "failed")
    unread = await _count_notifications(
        Notification.read_at.is_(None),
        Notification.status.notin_(("archived", "cancelled")),
    )
    templates = int(
        (
            await db.execute(
                select(func.count()).where(
                    NotificationTemplate.society_id == society_id,
                    NotificationTemplate.is_active.is_(True),
                )
            )
        ).scalar_one()
    )
    scheduled = int(
        (
            await db.execute(
                select(func.count()).where(
                    ScheduledNotification.society_id == society_id,
                    ScheduledNotification.status == "scheduled",
                    ScheduledNotification.is_active.is_(True),
                )
            )
        ).scalar_one()
    )
    today_count = await _count_notifications(Notification.created_at >= today_start)

    by_status = (
        await db.execute(
            select(Notification.status, func.count(Notification.id))
            .where(Notification.society_id == society_id, Notification.is_active.is_(True))
            .group_by(Notification.status)
        )
    ).all()

    by_channel = (
        await db.execute(
            select(NotificationDelivery.channel, func.count(NotificationDelivery.id))
            .where(NotificationDelivery.society_id == society_id)
            .group_by(NotificationDelivery.channel)
        )
    ).all()

    recent_rows = (
        await db.execute(
            select(Notification)
            .where(Notification.society_id == society_id, Notification.is_active.is_(True))
            .order_by(Notification.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return {
        "totalNotifications": total,
        "total": total,
        "queued": queued,
        "delivered": delivered,
        "failed": failed,
        "unread": unread,
        "scheduled": scheduled,
        "templates": templates,
        "totalTemplates": templates,
        "todayCount": today_count,
        "sentToday": today_count,
        "byStatus": [{"status": s, "count": int(c)} for s, c in by_status],
        "statusBreakdown": [{"status": s, "count": int(c)} for s, c in by_status],
        "byChannel": [{"channel": ch, "count": int(c)} for ch, c in by_channel],
        "channelUsage": [{"channel": ch, "count": int(c)} for ch, c in by_channel],
        "recentNotifications": [notification_to_dict(n) for n in recent_rows],
        "recent": [notification_to_dict(n) for n in recent_rows],
    }
