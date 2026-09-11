"""Notice business logic — create through publish/lifecycle/read/ack (Phase 11)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.notice import (
    Notice,
    NoticeAcknowledgement,
    NoticeAttachment,
    NoticeRead,
    NoticeTarget,
)
from Models.resident import Resident
from Schemas.common import build_pagination_meta
from Schemas.notice import (
    NoticeAttachmentIn,
    NoticeCancelRequest,
    NoticeCreate,
    NoticeListQueryParams,
    NoticePinRequest,
    NoticeTargetIn,
    NoticeTargetsReplace,
    NoticeUpdate,
    ResidentNoticeListQueryParams,
)
from Services.notice_helpers import (
    RESIDENT_VISIBLE_STATUSES,
    do_publish,
    apply_due_transitions,
    apply_lazy_transition_single,
    enforce_finance_category,
    get_active_targets,
    get_max_pinned,
    get_notice_in_society,
    get_resident_visible_notice_ids,
    get_society_settings,
    maybe_force_acknowledgement,
    next_notice_number,
    notice_to_dict,
    require_society_id,
    resolve_audience_resident_ids,
    resolve_resident_context,
    attachment_to_dict,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

FIELD_MAP = {
    "title": "title",
    "summary": "summary",
    "bodyText": "body_text",
    "bodyHtml": "body_html",
    "category": "category",
    "priority": "priority",
    "publishAt": "publish_at",
    "expiresAt": "expires_at",
    "pinUntil": "pin_until",
    "requiresAcknowledgement": "requires_acknowledgement",
    "acknowledgementDueAt": "acknowledgement_due_at",
    "notes": "notes",
    "metadata": "metadata_json",
}
RESTRICTED_AFTER_PUBLISH = {
    "title",
    "summary",
    "bodyText",
    "bodyHtml",
    "notes",
    "metadata",
    "requiresAcknowledgement",
    "acknowledgementDueAt",
    "expiresAt",
}
CANCELABLE_STATUSES = {"draft", "scheduled", "published"}


async def _create_targets(
    db: AsyncSession,
    notice: Notice,
    targets_in: List[NoticeTargetIn],
    *,
    actor_id: UUID,
    society_id: UUID,
) -> None:
    from Services.notice_helpers import validate_targets

    validated = await validate_targets(db, targets_in, society_id=society_id)
    for t in validated:
        row = NoticeTarget(
            society_id=society_id,
            notice_id=notice.id,
            target_type=t.targetType,
            building_id=t.buildingId,
            wing_id=t.wingId,
            flat_id=t.flatId,
            resident_id=t.residentId,
            committee_role=t.committeeRole,
            is_active=True,
            version=1,
        )
        apply_create_audit(row, actor_id)
        db.add(row)
    await db.flush()


async def _create_attachments(
    db: AsyncSession,
    notice: Notice,
    attachments: List[NoticeAttachmentIn],
    *,
    actor_id: UUID,
) -> None:
    for item in attachments:
        att = NoticeAttachment(
            notice_id=notice.id,
            file_name=item.fileName,
            file_url=item.fileUrl,
            mime_type=item.mimeType,
            file_size_bytes=item.fileSizeBytes,
            sort_order=item.sortOrder,
            uploaded_by=actor_id,
            is_active=True,
            version=1,
        )
        apply_create_audit(att, actor_id)
        db.add(att)


# ---------------------------------------------------------------------------
# Admin CRUD & lifecycle
# ---------------------------------------------------------------------------


async def create_notice(
    db: AsyncSession,
    body: NoticeCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    if actor_role == "finance" and body.category != "finance":
        raise ApiError(403, "Finance role can only create finance-category notices")

    notice_number = await next_notice_number(db, society_id)
    notice = Notice(
        society_id=society_id,
        notice_number=notice_number,
        title=body.title,
        summary=body.summary,
        body_text=body.bodyText,
        body_html=body.bodyHtml,
        category=body.category,
        priority=body.priority,
        status="draft",
        publish_at=body.publishAt,
        expires_at=body.expiresAt,
        is_pinned=False,
        pin_until=None,
        requires_acknowledgement=body.requiresAcknowledgement,
        acknowledgement_due_at=body.acknowledgementDueAt,
        published_by_user_id=None,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    settings = await get_society_settings(db, society_id)
    maybe_force_acknowledgement(notice, settings)
    apply_create_audit(notice, actor_id)
    db.add(notice)
    await db.flush()

    if body.targets:
        await _create_targets(db, notice, body.targets, actor_id=actor_id, society_id=society_id)
    if body.attachments:
        await _create_attachments(db, notice, body.attachments, actor_id=actor_id)

    await db.commit()
    await db.refresh(notice)

    publish_simple(
        "NoticeCreated",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "category": notice.category, "priority": notice.priority},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def list_notices(
    db: AsyncSession,
    query: NoticeListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    await apply_due_transitions(db, society_id)

    base = select(Notice).where(Notice.society_id == society_id)
    if query.building_id:
        base = base.join(NoticeTarget, NoticeTarget.notice_id == Notice.id).where(
            NoticeTarget.is_active.is_(True),
            NoticeTarget.target_type == "building",
            NoticeTarget.building_id == query.building_id,
        )
    if query.status:
        base = base.where(Notice.status == query.status)
    if query.category:
        base = base.where(Notice.category == query.category)
    if query.priority:
        base = base.where(Notice.priority == query.priority)
    if query.is_pinned is not None:
        base = base.where(Notice.is_pinned == query.is_pinned)
    if query.is_active is not None:
        base = base.where(Notice.is_active == query.is_active)
    if query.from_date:
        base = base.where(Notice.created_at >= query.from_date)
    if query.to_date:
        base = base.where(Notice.created_at <= query.to_date)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                Notice.title.ilike(term),
                Notice.body_text.ilike(term),
                Notice.notice_number.ilike(term),
            )
        )

    allowed_sort = (
        "created_at",
        "updated_at",
        "publish_at",
        "expires_at",
        "priority",
        "status",
        "title",
        "notice_number",
    )
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Notice, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()

    return {
        "notices": [notice_to_dict(n) for n in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_notice(db: AsyncSession, notice_id: UUID, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    await apply_lazy_transition_single(db, notice, society_id=society_id)

    targets = await get_active_targets(db, notice.id)
    attachments = (
        await db.execute(
            select(NoticeAttachment)
            .where(NoticeAttachment.notice_id == notice.id, NoticeAttachment.is_active.is_(True))
            .order_by(NoticeAttachment.sort_order.asc())
        )
    ).scalars().all()
    read_count = int(
        (await db.execute(select(func.count()).where(NoticeRead.notice_id == notice.id))).scalar_one()
    )
    ack_count = int(
        (
            await db.execute(select(func.count()).where(NoticeAcknowledgement.notice_id == notice.id))
        ).scalar_one()
    )
    audience_count = notice.audience_count_snapshot
    if audience_count is None and notice.status in {"published", "expired"}:
        audience_count = len(
            await resolve_audience_resident_ids(
                db,
                society_id=society_id,
                targets=targets,
                include_domestic_help=bool((notice.metadata_json or {}).get("includeDomesticHelp")),
            )
        )

    return {
        "notice": notice_to_dict(
            notice,
            targets=targets,
            attachments=attachments,
            read_count=read_count,
            ack_count=ack_count,
            audience_count=audience_count,
        )
    }


async def update_notice(
    db: AsyncSession,
    notice_id: UUID,
    body: NoticeUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    if notice.status in {"archived", "cancelled"}:
        raise ApiError(422, f"Notice is {notice.status} and cannot be updated")
    enforce_finance_category(actor_role, notice.category)

    data = body.model_dump(exclude_unset=True)
    if "category" in data and actor_role == "finance" and data["category"] != "finance":
        raise ApiError(403, "Finance role cannot change category away from finance")

    if notice.status == "published":
        allowed_extra = {"category", "priority"} if actor_role == "admin" else set()
        disallowed = set(data.keys()) - RESTRICTED_AFTER_PUBLISH - allowed_extra
        if disallowed:
            raise ApiError(422, f"Cannot update fields after publish: {', '.join(sorted(disallowed))}")

    changed_fields = []
    for api_key, orm_key in FIELD_MAP.items():
        if api_key in data:
            setattr(notice, orm_key, data[api_key])
            changed_fields.append(api_key)

    if notice.publish_at and notice.expires_at and notice.expires_at <= notice.publish_at:
        raise ApiError(422, "expiresAt must be after publishAt")

    settings = await get_society_settings(db, society_id)
    maybe_force_acknowledgement(notice, settings)

    if notice.status == "scheduled" and notice.publish_at and notice.publish_at <= utcnow():
        await do_publish(db, notice, actor_id=actor_id, society_id=society_id)
    else:
        apply_update_audit(notice, actor_id)

    await db.commit()
    if changed_fields:
        publish_simple(
            "NoticeUpdated",
            society_id=society_id,
            entity_type="notice",
            entity_id=notice.id,
            actor_id=actor_id,
            payload={"noticeId": str(notice.id), "changedFields": changed_fields},
        )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def publish_notice(
    db: AsyncSession,
    notice_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    enforce_finance_category(actor_role, notice.category)
    if notice.status not in {"draft", "scheduled"}:
        raise ApiError(422, "Notice cannot be published from current status")
    if not notice.title or not notice.title.strip():
        raise ApiError(422, "Title is required to publish")
    if not notice.body_text or not notice.body_text.strip():
        raise ApiError(422, "Body text is required to publish")

    targets = await get_active_targets(db, notice.id)
    if not targets:
        raise ApiError(422, "At least one active target is required to publish")

    settings = await get_society_settings(db, society_id)
    maybe_force_acknowledgement(notice, settings)

    if notice.publish_at is None or notice.publish_at <= utcnow():
        await do_publish(db, notice, actor_id=actor_id, society_id=society_id)
    else:
        notice.status = "scheduled"
        apply_update_audit(notice, actor_id)

    await db.commit()
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def cancel_notice(
    db: AsyncSession,
    notice_id: UUID,
    body: Optional[NoticeCancelRequest],
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    enforce_finance_category(actor_role, notice.category)
    if notice.status not in CANCELABLE_STATUSES:
        raise ApiError(422, "Notice cannot be cancelled from current status")

    reason = body.reason if body else None
    if notice.status == "published" and not reason:
        raise ApiError(422, "reason is required to cancel a published notice")

    notice.status = "cancelled"
    notice.cancelled_at = utcnow()
    notice.cancel_reason = reason
    notice.is_active = False
    if notice.is_pinned:
        notice.is_pinned = False
        notice.pin_until = None
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeCancelled",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "reason": reason},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def archive_notice(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    if notice.status not in {"published", "expired"}:
        raise ApiError(422, "Only published or expired notices can be archived")

    notice.status = "archived"
    notice.archived_at = utcnow()
    if notice.is_pinned:
        notice.is_pinned = False
        notice.pin_until = None
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeArchived",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id)},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def pin_notice(
    db: AsyncSession,
    notice_id: UUID,
    body: Optional[NoticePinRequest],
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    if notice.status != "published":
        raise ApiError(422, "Only published notices can be pinned")

    if not notice.is_pinned:
        settings = await get_society_settings(db, society_id)
        max_pinned = get_max_pinned(settings)
        current_pinned = int(
            (
                await db.execute(
                    select(func.count()).where(
                        Notice.society_id == society_id,
                        Notice.is_pinned.is_(True),
                        Notice.is_active.is_(True),
                    )
                )
            ).scalar_one()
        )
        if current_pinned >= max_pinned:
            raise ApiError(
                422, f"Maximum pinned notices ({max_pinned}) reached; unpin another notice first"
            )

    notice.is_pinned = True
    notice.pin_until = body.pinUntil if body else None
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticePinned",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id)},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def unpin_notice(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    notice.is_pinned = False
    notice.pin_until = None
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeUnpinned",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "reason": "manual"},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def replace_targets(
    db: AsyncSession,
    notice_id: UUID,
    body: NoticeTargetsReplace,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    enforce_finance_category(actor_role, notice.category)
    if notice.status not in {"draft", "scheduled"}:
        raise ApiError(422, "Targets are frozen once a notice is published")

    existing = await get_active_targets(db, notice.id)
    for t in existing:
        t.is_active = False
        apply_update_audit(t, actor_id)

    await _create_targets(db, notice, body.targets, actor_id=actor_id, society_id=society_id)
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeUpdated",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "changedFields": ["targets"]},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def add_attachment(
    db: AsyncSession,
    notice_id: UUID,
    body: NoticeAttachmentIn,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    enforce_finance_category(actor_role, notice.category)
    if notice.status in {"archived", "cancelled"}:
        raise ApiError(422, "Cannot add attachments to an archived or cancelled notice")

    att = NoticeAttachment(
        notice_id=notice.id,
        file_name=body.fileName,
        file_url=body.fileUrl,
        mime_type=body.mimeType,
        file_size_bytes=body.fileSizeBytes,
        sort_order=body.sortOrder,
        uploaded_by=actor_id,
        is_active=True,
        version=1,
    )
    apply_create_audit(att, actor_id)
    db.add(att)
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeUpdated",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "changedFields": ["attachments"]},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def remove_attachment(
    db: AsyncSession,
    notice_id: UUID,
    attachment_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    att = (
        await db.execute(
            select(NoticeAttachment).where(
                NoticeAttachment.id == attachment_id, NoticeAttachment.notice_id == notice.id
            )
        )
    ).scalar_one_or_none()
    if not att:
        raise ApiError(404, "Attachment not found")

    att.is_active = False
    apply_update_audit(att, actor_id)
    apply_update_audit(notice, actor_id)
    await db.commit()

    publish_simple(
        "NoticeUpdated",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload={"noticeId": str(notice.id), "changedFields": ["attachments"]},
    )
    return await get_notice(db, notice.id, actor_society_id=society_id)


async def get_reads(
    db: AsyncSession, notice_id: UUID, *, actor_society_id: UUID | None, page: int = 1, page_size: int = 20
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    base = select(NoticeRead).where(NoticeRead.notice_id == notice.id)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(NoticeRead.first_read_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    resident_ids = {r.resident_id for r in rows}
    residents: Dict[UUID, Resident] = {}
    if resident_ids:
        residents = {
            x.id: x
            for x in (await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))).scalars().all()
        }

    return {
        "reads": [
            {
                "id": str(r.id),
                "noticeId": str(r.notice_id),
                "residentId": str(r.resident_id),
                "residentName": residents[r.resident_id].name if r.resident_id in residents else None,
                "firstReadAt": r.first_read_at.isoformat(),
                "lastReadAt": r.last_read_at.isoformat(),
                "readCount": r.read_count,
                "readSource": r.read_source,
            }
            for r in rows
        ],
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def get_acknowledgements(
    db: AsyncSession, notice_id: UUID, *, actor_society_id: UUID | None, page: int = 1, page_size: int = 20
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    base = select(NoticeAcknowledgement).where(NoticeAcknowledgement.notice_id == notice.id)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(NoticeAcknowledgement.acknowledged_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    resident_ids = {r.resident_id for r in rows}
    residents: Dict[UUID, Resident] = {}
    if resident_ids:
        residents = {
            x.id: x
            for x in (await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))).scalars().all()
        }

    return {
        "acknowledgements": [
            {
                "id": str(a.id),
                "noticeId": str(a.notice_id),
                "residentId": str(a.resident_id),
                "residentName": residents[a.resident_id].name if a.resident_id in residents else None,
                "acknowledgedAt": a.acknowledged_at.isoformat(),
                "ackSource": a.ack_source,
            }
            for a in rows
        ],
        "pagination": build_pagination_meta(page, page_size, total),
    }


async def process_due_notices(
    db: AsyncSession, *, actor_society_id: UUID | None, actor_id: UUID | None = None
) -> Dict[str, int]:
    society_id = require_society_id(actor_society_id)
    return await apply_due_transitions(db, society_id, actor_id=actor_id)


# ---------------------------------------------------------------------------
# Resident portal
# ---------------------------------------------------------------------------


async def resident_list_notices(
    db: AsyncSession,
    query: ResidentNoticeListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    view: Optional[str] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    await apply_due_transitions(db, society_id)

    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if not visible_ids:
        return {"notices": [], "pagination": build_pagination_meta(query.page, query.page_size, 0)}

    effective_view = (view or query.view or "inbox").lower()
    base = select(Notice).where(
        Notice.society_id == society_id, Notice.id.in_(visible_ids), Notice.is_active.is_(True)
    )

    if effective_view == "archive":
        base = base.where(Notice.status.in_(("expired", "archived")))
    else:
        base = base.where(Notice.status == "published")

    if effective_view == "pinned":
        base = base.where(Notice.is_pinned.is_(True))

    if query.category:
        base = base.where(Notice.category == query.category)
    if query.priority:
        base = base.where(Notice.priority == query.priority)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                Notice.title.ilike(term),
                Notice.summary.ilike(term),
                Notice.notice_number.ilike(term),
            )
        )

    read_notice_ids = set(
        (
            await db.execute(
                select(NoticeRead.notice_id).where(
                    NoticeRead.resident_id == resident.id, NoticeRead.notice_id.in_(visible_ids)
                )
            )
        ).scalars().all()
    )
    if (effective_view == "unread" or query.unread_only) and read_notice_ids:
        base = base.where(Notice.id.notin_(read_notice_ids))

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()

    row_ids = {n.id for n in rows}
    ack_notice_ids = set()
    if row_ids:
        ack_notice_ids = set(
            (
                await db.execute(
                    select(NoticeAcknowledgement.notice_id).where(
                        NoticeAcknowledgement.resident_id == resident.id,
                        NoticeAcknowledgement.notice_id.in_(row_ids),
                    )
                )
            ).scalars().all()
        )

    return {
        "notices": [
            notice_to_dict(n, is_read=n.id in read_notice_ids, is_acknowledged=n.id in ack_notice_ids)
            for n in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def _mark_read_internal(
    db: AsyncSession, notice: Notice, *, resident_id: UUID, society_id: UUID
) -> bool:
    existing = (
        await db.execute(
            select(NoticeRead).where(
                NoticeRead.notice_id == notice.id, NoticeRead.resident_id == resident_id
            )
        )
    ).scalar_one_or_none()
    now = utcnow()
    first = False
    if existing:
        existing.last_read_at = now
        existing.read_count += 1
    else:
        existing = NoticeRead(
            society_id=society_id,
            notice_id=notice.id,
            resident_id=resident_id,
            first_read_at=now,
            last_read_at=now,
            read_count=1,
            read_source="portal",
            metadata_json={},
        )
        db.add(existing)
        first = True
    await db.commit()
    if first:
        publish_simple(
            "NoticeRead",
            society_id=society_id,
            entity_type="notice",
            entity_id=notice.id,
            actor_id=resident_id,
            payload={"noticeId": str(notice.id), "residentId": str(resident_id)},
        )
    return first


async def resident_get_notice(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    await apply_due_transitions(db, society_id)

    notice = await get_notice_in_society(db, notice_id, society_id)
    if notice.status not in RESIDENT_VISIBLE_STATUSES:
        raise ApiError(404, "Notice not found")

    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if notice.id not in visible_ids:
        raise ApiError(404, "Notice not found")

    await _mark_read_internal(db, notice, resident_id=resident.id, society_id=society_id)

    attachments = (
        await db.execute(
            select(NoticeAttachment)
            .where(NoticeAttachment.notice_id == notice.id, NoticeAttachment.is_active.is_(True))
            .order_by(NoticeAttachment.sort_order.asc())
        )
    ).scalars().all()
    is_acked = (
        await db.execute(
            select(NoticeAcknowledgement).where(
                NoticeAcknowledgement.notice_id == notice.id,
                NoticeAcknowledgement.resident_id == resident.id,
            )
        )
    ).scalar_one_or_none() is not None

    return {
        "notice": notice_to_dict(
            notice, attachments=attachments, is_read=True, is_acknowledged=is_acked
        )
    }


async def resident_mark_read(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if notice.id not in visible_ids or notice.status not in RESIDENT_VISIBLE_STATUSES:
        raise ApiError(404, "Notice not found")

    await _mark_read_internal(db, notice, resident_id=resident.id, society_id=society_id)
    return {"noticeId": str(notice.id), "read": True}


async def resident_acknowledge(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if notice.id not in visible_ids:
        raise ApiError(404, "Notice not found")
    if notice.status not in {"published", "expired"}:
        raise ApiError(422, "Notice is not open for acknowledgement")

    existing = (
        await db.execute(
            select(NoticeAcknowledgement).where(
                NoticeAcknowledgement.notice_id == notice.id,
                NoticeAcknowledgement.resident_id == resident.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {
            "noticeId": str(notice.id),
            "acknowledged": True,
            "acknowledgedAt": existing.acknowledged_at.isoformat(),
        }

    now = utcnow()
    ack = NoticeAcknowledgement(
        society_id=society_id,
        notice_id=notice.id,
        resident_id=resident.id,
        acknowledged_at=now,
        ack_source="portal",
        metadata_json={},
    )
    db.add(ack)
    await db.commit()

    publish_simple(
        "NoticeAcknowledged",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=resident.id,
        payload={"noticeId": str(notice.id), "residentId": str(resident.id), "acknowledgedAt": now.isoformat()},
    )
    return {"noticeId": str(notice.id), "acknowledged": True, "acknowledgedAt": now.isoformat()}


async def resident_list_attachments(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    notice = await get_notice_in_society(db, notice_id, society_id)
    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if notice.id not in visible_ids or notice.status not in RESIDENT_VISIBLE_STATUSES:
        raise ApiError(404, "Notice not found")

    attachments = (
        await db.execute(
            select(NoticeAttachment)
            .where(NoticeAttachment.notice_id == notice.id, NoticeAttachment.is_active.is_(True))
            .order_by(NoticeAttachment.sort_order.asc())
        )
    ).scalars().all()
    return {"attachments": [attachment_to_dict(a) for a in attachments]}


async def resident_dashboard_summary(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None, pinned_limit: int = 5
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    await apply_due_transitions(db, society_id)

    visible_ids = await get_resident_visible_notice_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if not visible_ids:
        return {"unreadCount": 0, "pinnedNotices": []}

    read_ids = set(
        (
            await db.execute(
                select(NoticeRead.notice_id).where(
                    NoticeRead.resident_id == resident.id, NoticeRead.notice_id.in_(visible_ids)
                )
            )
        ).scalars().all()
    )

    published_stmt = select(Notice).where(
        Notice.society_id == society_id,
        Notice.id.in_(visible_ids),
        Notice.status == "published",
        Notice.is_active.is_(True),
    )
    unread_stmt = published_stmt
    if read_ids:
        unread_stmt = unread_stmt.where(Notice.id.notin_(read_ids))
    unread_count = int(
        (await db.execute(select(func.count()).select_from(unread_stmt.subquery()))).scalar_one()
    )

    pinned_rows = (
        await db.execute(
            published_stmt.where(Notice.is_pinned.is_(True))
            .order_by(Notice.created_at.desc())
            .limit(pinned_limit)
        )
    ).scalars().all()

    return {
        "unreadCount": unread_count,
        "pinnedNotices": [notice_to_dict(n, is_read=n.id in read_ids) for n in pinned_rows],
    }
