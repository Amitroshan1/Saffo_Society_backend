"""Notice reports (Phase 11)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.notice import Notice, NoticeAcknowledgement, NoticeRead
from Models.resident import Resident
from Services.notice_helpers import get_active_targets, require_society_id, resolve_audience_resident_ids
from Utils.errors import ApiError

REPORT_KEYS = {
    "read-percentage",
    "unread-residents",
    "acknowledgement-status",
    "published-notices",
    "expired-notices",
    "category-summary",
    "priority-summary",
}


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label} date") from exc


def _parse_uuid(value: Optional[str], label: str) -> Optional[UUID]:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label}") from exc


async def _audience_count(db: AsyncSession, notice: Notice, society_id: UUID) -> int:
    if notice.audience_count_snapshot is not None:
        return notice.audience_count_snapshot
    targets = await get_active_targets(db, notice.id)
    return len(
        await resolve_audience_resident_ids(
            db,
            society_id=society_id,
            targets=targets,
            include_domestic_help=bool((notice.metadata_json or {}).get("includeDomesticHelp")),
        )
    )


async def run_report(
    db: AsyncSession,
    report_key: str,
    *,
    actor_society_id: UUID | None,
    filters: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    key = report_key.strip().lower().replace("_", "-")
    if key not in REPORT_KEYS:
        raise ApiError(404, f"Unknown report: {report_key}")

    handlers = {
        "read-percentage": _read_percentage,
        "unread-residents": _unread_residents,
        "acknowledgement-status": _acknowledgement_status,
        "published-notices": _published_notices,
        "expired-notices": _expired_notices,
        "category-summary": _category_summary,
        "priority-summary": _priority_summary,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


async def _read_percentage(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    notice_id = _parse_uuid(filters.get("noticeId"), "noticeId")
    stmt = select(Notice).where(
        Notice.society_id == society_id,
        Notice.status.in_(("published", "expired")),
        Notice.is_active.is_(True),
    )
    if notice_id:
        stmt = stmt.where(Notice.id == notice_id)
    notices = (await db.execute(stmt.order_by(Notice.published_at.desc()))).scalars().all()

    rows = []
    for n in notices:
        audience = await _audience_count(db, n, society_id)
        read_count = int(
            (await db.execute(select(func.count()).where(NoticeRead.notice_id == n.id))).scalar_one()
        )
        percent = round((read_count / audience) * 100, 2) if audience else 0.0
        rows.append(
            {
                "noticeId": str(n.id),
                "noticeNumber": n.notice_number,
                "title": n.title,
                "audienceCount": audience,
                "readCount": read_count,
                "readPercent": percent,
            }
        )
    return rows


async def _unread_residents(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    notice_id = _parse_uuid(filters.get("noticeId"), "noticeId")
    if not notice_id:
        raise ApiError(422, "noticeId is required")
    notice = (
        await db.execute(select(Notice).where(Notice.id == notice_id, Notice.society_id == society_id))
    ).scalar_one_or_none()
    if not notice:
        raise ApiError(404, "Notice not found")

    targets = await get_active_targets(db, notice.id)
    audience_ids = await resolve_audience_resident_ids(
        db,
        society_id=society_id,
        targets=targets,
        include_domestic_help=bool((notice.metadata_json or {}).get("includeDomesticHelp")),
    )
    read_ids = set(
        (
            await db.execute(select(NoticeRead.resident_id).where(NoticeRead.notice_id == notice.id))
        ).scalars().all()
    )
    unread_ids = audience_ids - read_ids
    if not unread_ids:
        return []

    residents = (await db.execute(select(Resident).where(Resident.id.in_(unread_ids)))).scalars().all()
    return [{"residentId": str(r.id), "residentName": r.name, "residentCode": r.code} for r in residents]


async def _acknowledgement_status(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    notice_id = _parse_uuid(filters.get("noticeId"), "noticeId")
    stmt = select(Notice).where(
        Notice.society_id == society_id,
        Notice.requires_acknowledgement.is_(True),
        Notice.status.in_(("published", "expired")),
        Notice.is_active.is_(True),
    )
    if notice_id:
        stmt = stmt.where(Notice.id == notice_id)
    notices = (await db.execute(stmt)).scalars().all()
    now = datetime.now(timezone.utc)

    rows = []
    for n in notices:
        audience = await _audience_count(db, n, society_id)
        ack_count = int(
            (
                await db.execute(select(func.count()).where(NoticeAcknowledgement.notice_id == n.id))
            ).scalar_one()
        )
        overdue = bool(n.acknowledgement_due_at and n.acknowledgement_due_at <= now and ack_count < audience)
        rows.append(
            {
                "noticeId": str(n.id),
                "noticeNumber": n.notice_number,
                "title": n.title,
                "audienceCount": audience,
                "acknowledgedCount": ack_count,
                "pendingCount": max(0, audience - ack_count),
                "overdue": overdue,
            }
        )
    return rows


async def _published_notices(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = select(Notice).where(
        Notice.society_id == society_id, Notice.status.in_(("published", "expired", "archived"))
    )
    if from_d:
        stmt = stmt.where(Notice.published_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc))
    if to_d:
        stmt = stmt.where(Notice.published_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc))
    notices = (await db.execute(stmt.order_by(Notice.published_at.desc()))).scalars().all()
    return [
        {
            "noticeId": str(n.id),
            "noticeNumber": n.notice_number,
            "title": n.title,
            "category": n.category,
            "priority": n.priority,
            "publishedAt": n.published_at.isoformat() if n.published_at else None,
        }
        for n in notices
    ]


async def _expired_notices(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = select(Notice).where(Notice.society_id == society_id, Notice.status == "expired")
    if from_d:
        stmt = stmt.where(Notice.expired_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc))
    if to_d:
        stmt = stmt.where(Notice.expired_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc))
    notices = (await db.execute(stmt.order_by(Notice.expired_at.desc()))).scalars().all()
    return [
        {
            "noticeId": str(n.id),
            "noticeNumber": n.notice_number,
            "title": n.title,
            "category": n.category,
            "expiredAt": n.expired_at.isoformat() if n.expired_at else None,
        }
        for n in notices
    ]


async def _category_summary(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Notice.category, func.count())
            .where(Notice.society_id == society_id, Notice.is_active.is_(True))
            .group_by(Notice.category)
        )
    ).all()
    return [{"category": c, "count": int(cnt)} for c, cnt in rows]


async def _priority_summary(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Notice.priority, func.count())
            .where(Notice.society_id == society_id, Notice.is_active.is_(True))
            .group_by(Notice.priority)
        )
    ).all()
    return [{"priority": p, "count": int(cnt)} for p, cnt in rows]
