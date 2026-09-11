"""Notification reports (Phase 15)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.notification import Notification, NotificationDelivery, ScheduledNotification
from Services.notification_helpers import require_society_id
from Utils.errors import ApiError

REPORT_KEYS = {
    "summary",
    "delivery_success",
    "failed_deliveries",
    "channel_usage",
    "read_rate",
    "unread",
    "scheduled",
    "volume",
}


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label} date") from exc


async def run_report(
    db: AsyncSession,
    report_key: str,
    *,
    actor_society_id: UUID | None,
    filters: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    key = report_key.strip().lower().replace("-", "_")
    if key not in REPORT_KEYS:
        raise ApiError(404, f"Unknown report: {report_key}")

    handlers = {
        "summary": _summary,
        "delivery_success": _delivery_success,
        "failed_deliveries": _failed_deliveries,
        "channel_usage": _channel_usage,
        "read_rate": _read_rate,
        "unread": _unread,
        "scheduled": _scheduled,
        "volume": _volume,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


async def _summary(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    total = int(
        (
            await db.execute(
                select(func.count()).where(
                    Notification.society_id == society_id, Notification.is_active.is_(True)
                )
            )
        ).scalar_one()
    )
    delivered = int(
        (
            await db.execute(
                select(func.count()).where(
                    Notification.society_id == society_id,
                    Notification.status == "delivered",
                )
            )
        ).scalar_one()
    )
    failed = int(
        (
            await db.execute(
                select(func.count()).where(
                    Notification.society_id == society_id, Notification.status == "failed"
                )
            )
        ).scalar_one()
    )
    return [
        {
            "metric": "total",
            "value": total,
        },
        {
            "metric": "delivered",
            "value": delivered,
        },
        {
            "metric": "failed",
            "value": failed,
        },
        {
            "metric": "successRate",
            "value": round((delivered / total) * 100, 2) if total else 0.0,
        },
    ]


async def _delivery_success(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    base = select(NotificationDelivery).where(NotificationDelivery.society_id == society_id)
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    if from_d:
        base = base.where(cast(NotificationDelivery.created_at, Date) >= from_d)
    if to_d:
        base = base.where(cast(NotificationDelivery.created_at, Date) <= to_d)

    rows = (
        await db.execute(
            select(NotificationDelivery.status, func.count(NotificationDelivery.id))
            .where(NotificationDelivery.society_id == society_id)
            .group_by(NotificationDelivery.status)
        )
    ).all()
    return [{"status": status, "count": int(count)} for status, count in rows]


async def _failed_deliveries(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.society_id == society_id,
                NotificationDelivery.status == "failed",
            )
            .order_by(NotificationDelivery.updated_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return [
        {
            "deliveryId": str(d.id),
            "notificationId": str(d.notification_id),
            "channel": d.channel,
            "attemptCount": d.attempt_count,
            "errorMessage": d.error_message,
            "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in rows
    ]


async def _channel_usage(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(NotificationDelivery.channel, func.count(NotificationDelivery.id))
            .where(NotificationDelivery.society_id == society_id)
            .group_by(NotificationDelivery.channel)
        )
    ).all()
    return [{"channel": ch, "count": int(cnt)} for ch, cnt in rows]


async def _read_rate(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    total = int(
        (
            await db.execute(
                select(func.count()).where(
                    Notification.society_id == society_id,
                    Notification.is_active.is_(True),
                    Notification.status.in_(("delivered", "read")),
                )
            )
        ).scalar_one()
    )
    read = int(
        (
            await db.execute(
                select(func.count()).where(
                    Notification.society_id == society_id,
                    Notification.read_at.is_not(None),
                )
            )
        ).scalar_one()
    )
    return [
        {"metric": "deliveredOrRead", "value": total},
        {"metric": "read", "value": read},
        {"metric": "readRate", "value": round((read / total) * 100, 2) if total else 0.0},
    ]


async def _unread(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Notification)
            .where(
                Notification.society_id == society_id,
                Notification.read_at.is_(None),
                Notification.is_active.is_(True),
                Notification.status.notin_(("archived", "cancelled")),
            )
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return [
        {
            "notificationId": str(n.id),
            "title": n.title,
            "category": n.category,
            "priority": n.priority,
            "createdAt": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


async def _scheduled(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(ScheduledNotification)
            .where(
                ScheduledNotification.society_id == society_id,
                ScheduledNotification.is_active.is_(True),
            )
            .order_by(ScheduledNotification.schedule_at.asc())
            .limit(100)
        )
    ).scalars().all()
    return [
        {
            "scheduledId": str(s.id),
            "title": s.title,
            "status": s.status,
            "scheduleAt": s.schedule_at.isoformat() if s.schedule_at else None,
            "nextRunAt": s.next_run_at.isoformat() if s.next_run_at else None,
        }
        for s in rows
    ]


async def _volume(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to") or datetime.now(timezone.utc).date()
    if not from_d:
        from_d = to_d.replace(day=1)

    rows = (
        await db.execute(
            select(cast(Notification.created_at, Date), func.count(Notification.id))
            .where(
                Notification.society_id == society_id,
                cast(Notification.created_at, Date) >= from_d,
                cast(Notification.created_at, Date) <= to_d,
            )
            .group_by(cast(Notification.created_at, Date))
            .order_by(cast(Notification.created_at, Date))
        )
    ).all()
    return [{"date": d.isoformat(), "count": int(cnt)} for d, cnt in rows]
