"""Notice dashboard KPIs (Phase 11)."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.notice import Notice, NoticeAcknowledgement, NoticeRead, NoticeTarget
from Schemas.notice import NOTICE_CATEGORY_VALUES, NOTICE_PRIORITY_VALUES
from Services.notice_helpers import (
    apply_due_transitions,
    notice_to_dict,
    require_society_id,
    resolve_audience_resident_ids,
)


async def get_dashboard(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    await apply_due_transitions(db, society_id)

    async def _count(*clauses) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(
                        Notice.society_id == society_id, Notice.is_active.is_(True), *clauses
                    )
                )
            ).scalar_one()
        )

    published_count = await _count(Notice.status == "published")
    scheduled_count = await _count(Notice.status == "scheduled")
    expired_count = await _count(Notice.status == "expired")
    draft_count = await _count(Notice.status == "draft")
    pinned_count = await _count(Notice.is_pinned.is_(True))

    by_category = []
    for category in NOTICE_CATEGORY_VALUES:
        cnt = await _count(Notice.category == category)
        if cnt:
            by_category.append({"category": category, "count": cnt})

    by_priority = []
    for priority in NOTICE_PRIORITY_VALUES:
        cnt = await _count(Notice.priority == priority)
        if cnt:
            by_priority.append({"priority": priority, "count": cnt})

    engaged = (
        await db.execute(
            select(Notice).where(
                Notice.society_id == society_id,
                Notice.status.in_(("published", "expired")),
                Notice.is_active.is_(True),
            )
        )
    ).scalars().all()

    read_percentages: list[float] = []
    pending_ack_count = 0
    for notice in engaged:
        audience = notice.audience_count_snapshot
        if audience is None:
            targets = (
                await db.execute(
                    select(NoticeTarget).where(
                        NoticeTarget.notice_id == notice.id, NoticeTarget.is_active.is_(True)
                    )
                )
            ).scalars().all()
            audience = len(
                await resolve_audience_resident_ids(
                    db,
                    society_id=society_id,
                    targets=targets,
                    include_domestic_help=bool((notice.metadata_json or {}).get("includeDomesticHelp")),
                )
            )
        read_count = int(
            (await db.execute(select(func.count()).where(NoticeRead.notice_id == notice.id))).scalar_one()
        )
        if audience > 0:
            read_percentages.append((read_count / audience) * 100)

        if notice.requires_acknowledgement:
            ack_count = int(
                (
                    await db.execute(
                        select(func.count()).where(NoticeAcknowledgement.notice_id == notice.id)
                    )
                ).scalar_one()
            )
            pending_ack_count += max(0, audience - ack_count)

    avg_read_percent = round(sum(read_percentages) / len(read_percentages), 2) if read_percentages else 0.0

    recent_rows = (
        await db.execute(
            select(Notice)
            .where(Notice.society_id == society_id, Notice.is_active.is_(True))
            .order_by(Notice.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    return {
        "publishedCount": published_count,
        "scheduledCount": scheduled_count,
        "expiredCount": expired_count,
        "draftCount": draft_count,
        "pinnedCount": pinned_count,
        "avgReadPercent": avg_read_percent,
        "pendingAckCount": pending_ack_count,
        "byCategory": by_category,
        "byPriority": by_priority,
        "recentNotices": [notice_to_dict(n) for n in recent_rows],
    }
