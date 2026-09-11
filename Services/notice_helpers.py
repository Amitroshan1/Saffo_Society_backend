"""Notice helpers — lookups, targeting, audience resolution, lifecycle transitions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.building import Building
from Models.flat import Flat
from Models.notice import Notice, NoticeAttachment, NoticeTarget
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.society import Society
from Models.wing import Wing
from Schemas.notice import NoticeTargetIn
from Utils.audit import apply_update_audit, utcnow
from Utils.errors import ApiError

DEFAULT_MAX_PINNED = 5
RESIDENT_VISIBLE_STATUSES = {"published", "expired", "archived"}
GUARD_NOTICE_CATEGORIES = frozenset(
    {"emergency", "security", "parking", "water", "electricity"}
)
GUARD_NOTICE_PRIORITIES = frozenset({"high", "critical"})


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def enforce_finance_category(actor_role: str, category: str) -> None:
    if actor_role == "finance" and category != "finance":
        raise ApiError(403, "Finance role can only manage finance-category notices")


async def get_notice_in_society(db: AsyncSession, notice_id: UUID, society_id: UUID) -> Notice:
    result = await db.execute(
        select(Notice).where(Notice.id == notice_id, Notice.society_id == society_id)
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise ApiError(404, "Notice not found")
    return notice


async def get_active_targets(db: AsyncSession, notice_id: UUID) -> List[NoticeTarget]:
    rows = (
        await db.execute(
            select(NoticeTarget).where(
                NoticeTarget.notice_id == notice_id,
                NoticeTarget.is_active.is_(True),
            )
        )
    ).scalars().all()
    return list(rows)


async def next_notice_number(db: AsyncSession, society_id: UUID) -> str:
    count = (
        await db.execute(
            select(func.count()).where(Notice.society_id == society_id)
        )
    ).scalar_one()
    return f"NTC-{int(count) + 1:06d}"


async def get_society_settings(db: AsyncSession, society_id: UUID) -> Dict[str, Any]:
    society = (
        await db.execute(select(Society).where(Society.id == society_id))
    ).scalar_one_or_none()
    if not society:
        return {}
    return society.settings or {}


def get_max_pinned(settings: Dict[str, Any]) -> int:
    notices_settings = settings.get("notices") or {}
    try:
        return max(1, int(notices_settings.get("maxPinned", DEFAULT_MAX_PINNED)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_PINNED


def get_require_ack_for_critical(settings: Dict[str, Any]) -> bool:
    notices_settings = settings.get("notices") or {}
    return bool(notices_settings.get("requireAckForCritical", False))


def maybe_force_acknowledgement(notice: Notice, settings: Dict[str, Any]) -> None:
    if notice.priority == "critical" and get_require_ack_for_critical(settings):
        notice.requires_acknowledgement = True


async def validate_targets(
    db: AsyncSession, targets_in: Sequence[NoticeTargetIn], *, society_id: UUID
) -> List[NoticeTargetIn]:
    seen = set()
    validated: List[NoticeTargetIn] = []
    for t in targets_in:
        key = (t.targetType, t.buildingId, t.wingId, t.flatId, t.residentId, t.committeeRole)
        if key in seen:
            raise ApiError(422, "Duplicate target entries are not allowed")
        seen.add(key)

        if t.targetType == "building":
            building = (
                await db.execute(
                    select(Building).where(Building.id == t.buildingId, Building.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not building:
                raise ApiError(404, f"Building not found: {t.buildingId}")
        elif t.targetType == "wing":
            wing = (
                await db.execute(
                    select(Wing).where(Wing.id == t.wingId, Wing.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not wing:
                raise ApiError(404, f"Wing not found: {t.wingId}")
        elif t.targetType == "flat":
            flat = (
                await db.execute(
                    select(Flat).where(Flat.id == t.flatId, Flat.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not flat:
                raise ApiError(404, f"Flat not found: {t.flatId}")
        elif t.targetType == "resident":
            resident = (
                await db.execute(
                    select(Resident).where(Resident.id == t.residentId, Resident.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not resident:
                raise ApiError(404, f"Resident not found: {t.residentId}")
        validated.append(t)
    return validated


async def resolve_audience_resident_ids(
    db: AsyncSession,
    *,
    society_id: UUID,
    targets: Iterable[NoticeTarget],
    include_domestic_help: bool = False,
) -> set[UUID]:
    """Dynamic audience resolution — union of active occupancy residents across targets."""
    resident_ids: set[UUID] = set()
    direct_resident_ids: set[UUID] = set()

    for t in targets:
        if not t.is_active:
            continue
        if t.target_type == "committee_role":
            continue
        if t.target_type == "resident":
            if t.resident_id:
                direct_resident_ids.add(t.resident_id)
            continue

        stmt = select(Occupancy.resident_id).where(
            Occupancy.society_id == society_id,
            Occupancy.status == "active",
            Occupancy.is_active.is_(True),
        )
        if t.target_type == "building":
            stmt = stmt.where(Occupancy.building_id == t.building_id)
        elif t.target_type == "wing":
            stmt = stmt.where(Occupancy.wing_id == t.wing_id)
        elif t.target_type == "flat":
            stmt = stmt.where(Occupancy.flat_id == t.flat_id)
        elif t.target_type == "society":
            pass
        else:
            continue

        if not include_domestic_help:
            stmt = stmt.where(Occupancy.role != "domestic_help")

        rows = (await db.execute(stmt)).scalars().all()
        resident_ids.update(rows)

    if direct_resident_ids:
        active_rows = (
            await db.execute(
                select(Resident.id).where(
                    Resident.id.in_(direct_resident_ids),
                    Resident.society_id == society_id,
                    Resident.is_active.is_(True),
                )
            )
        ).scalars().all()
        resident_ids.update(active_rows)

    return resident_ids


async def get_resident_visible_notice_ids(
    db: AsyncSession,
    *,
    society_id: UUID,
    resident_id: UUID,
    occupancies: Sequence[Occupancy],
) -> set[UUID]:
    """Notice ids whose targets match this resident's scope (any status)."""
    normal_occ = [o for o in occupancies if o.role != "domestic_help"]
    dh_occ = [o for o in occupancies if o.role == "domestic_help"]

    normal_buildings = {o.building_id for o in normal_occ}
    normal_wings = {o.wing_id for o in normal_occ}
    normal_flats = {o.flat_id for o in normal_occ}
    dh_buildings = {o.building_id for o in dh_occ}
    dh_wings = {o.wing_id for o in dh_occ}
    dh_flats = {o.flat_id for o in dh_occ}

    include_dh_flag = (
        func.coalesce(Notice.metadata_json["includeDomesticHelp"].astext, "false") == "true"
    )

    clauses = [
        and_(NoticeTarget.target_type == "resident", NoticeTarget.resident_id == resident_id),
    ]
    if normal_occ:
        clauses.append(NoticeTarget.target_type == "society")
        if normal_buildings:
            clauses.append(
                and_(NoticeTarget.target_type == "building", NoticeTarget.building_id.in_(normal_buildings))
            )
        if normal_wings:
            clauses.append(and_(NoticeTarget.target_type == "wing", NoticeTarget.wing_id.in_(normal_wings)))
        if normal_flats:
            clauses.append(and_(NoticeTarget.target_type == "flat", NoticeTarget.flat_id.in_(normal_flats)))
    if dh_occ:
        clauses.append(and_(NoticeTarget.target_type == "society", include_dh_flag))
        if dh_buildings:
            clauses.append(
                and_(
                    NoticeTarget.target_type == "building",
                    NoticeTarget.building_id.in_(dh_buildings),
                    include_dh_flag,
                )
            )
        if dh_wings:
            clauses.append(
                and_(NoticeTarget.target_type == "wing", NoticeTarget.wing_id.in_(dh_wings), include_dh_flag)
            )
        if dh_flats:
            clauses.append(
                and_(NoticeTarget.target_type == "flat", NoticeTarget.flat_id.in_(dh_flats), include_dh_flag)
            )

    stmt = (
        select(NoticeTarget.notice_id)
        .join(Notice, Notice.id == NoticeTarget.notice_id)
        .where(
            NoticeTarget.society_id == society_id,
            NoticeTarget.is_active.is_(True),
            or_(*clauses),
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def resolve_resident_context(
    db: AsyncSession, *, actor_id: UUID, society_id: UUID
) -> tuple[Resident, List[Occupancy]]:
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

    occupancies = (
        await db.execute(
            select(Occupancy).where(
                Occupancy.society_id == society_id,
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not occupancies:
        raise ApiError(404, "Active occupancy not found for resident")
    return resident, list(occupancies)


# ---------------------------------------------------------------------------
# Lifecycle transitions (schedule -> publish, publish -> expire, unpin)
# ---------------------------------------------------------------------------


async def do_publish(
    db: AsyncSession, notice: Notice, *, actor_id: Optional[UUID], society_id: UUID
) -> None:
    now = utcnow()
    notice.status = "published"
    notice.published_at = now
    if actor_id:
        notice.published_by_user_id = actor_id
        apply_update_audit(notice, actor_id)

    targets = await get_active_targets(db, notice.id)
    audience = await resolve_audience_resident_ids(
        db,
        society_id=society_id,
        targets=targets,
        include_domestic_help=bool((notice.metadata_json or {}).get("includeDomesticHelp")),
    )
    notice.audience_count_snapshot = len(audience)
    notice_payload = {
        "noticeId": str(notice.id),
        "notice_title": notice.title,
        "category": notice.category,
        "priority": notice.priority,
        "publishAt": notice.publish_at.isoformat() if notice.publish_at else None,
        "audienceCount": notice.audience_count_snapshot,
        "requiresAck": notice.requires_acknowledgement,
    }
    publish_simple(
        "NoticePublished",
        society_id=society_id,
        entity_type="notice",
        entity_id=notice.id,
        actor_id=actor_id,
        payload=notice_payload,
    )
    if notice.category in GUARD_NOTICE_CATEGORIES or notice.priority in GUARD_NOTICE_PRIORITIES:
        publish_simple(
            "GuardNoticePublished",
            society_id=society_id,
            entity_type="notice",
            entity_id=notice.id,
            actor_id=actor_id,
            payload=notice_payload,
        )


async def _transition_if_due(
    db: AsyncSession, notice: Notice, *, society_id: UUID, actor_id: Optional[UUID]
) -> bool:
    now = utcnow()
    changed = False

    if notice.status == "scheduled" and notice.publish_at and notice.publish_at <= now:
        await do_publish(db, notice, actor_id=actor_id, society_id=society_id)
        changed = True
    elif notice.status == "published" and notice.expires_at and notice.expires_at <= now:
        notice.status = "expired"
        notice.expired_at = now
        if notice.is_pinned:
            notice.is_pinned = False
            notice.pin_until = None
        if actor_id:
            apply_update_audit(notice, actor_id)
        publish_simple(
            "NoticeExpired",
            society_id=society_id,
            entity_type="notice",
            entity_id=notice.id,
            actor_id=actor_id,
            payload={
                "noticeId": str(notice.id),
                "expiresAt": notice.expires_at.isoformat() if notice.expires_at else None,
            },
        )
        changed = True

    if notice.is_pinned and notice.pin_until and notice.pin_until <= now:
        notice.is_pinned = False
        notice.pin_until = None
        if actor_id:
            apply_update_audit(notice, actor_id)
        publish_simple(
            "NoticeUnpinned",
            society_id=society_id,
            entity_type="notice",
            entity_id=notice.id,
            actor_id=actor_id,
            payload={"noticeId": str(notice.id), "reason": "pin_until_elapsed"},
        )
        changed = True

    return changed


async def apply_lazy_transition_single(db: AsyncSession, notice: Notice, *, society_id: UUID) -> bool:
    changed = await _transition_if_due(db, notice, society_id=society_id, actor_id=None)
    if changed:
        await db.commit()
    return changed


async def apply_due_transitions(
    db: AsyncSession, society_id: UUID, *, actor_id: Optional[UUID] = None
) -> Dict[str, int]:
    now = utcnow()
    due = (
        await db.execute(
            select(Notice).where(
                Notice.society_id == society_id,
                Notice.is_active.is_(True),
                or_(
                    and_(
                        Notice.status == "scheduled",
                        Notice.publish_at.isnot(None),
                        Notice.publish_at <= now,
                    ),
                    and_(
                        Notice.status == "published",
                        Notice.expires_at.isnot(None),
                        Notice.expires_at <= now,
                    ),
                    and_(
                        Notice.is_pinned.is_(True),
                        Notice.pin_until.isnot(None),
                        Notice.pin_until <= now,
                    ),
                ),
            )
        )
    ).scalars().all()

    promoted = expired = unpinned = 0
    for notice in due:
        before_status, before_pinned = notice.status, notice.is_pinned
        await _transition_if_due(db, notice, society_id=society_id, actor_id=actor_id)
        if before_status == "scheduled" and notice.status == "published":
            promoted += 1
        if before_status == "published" and notice.status == "expired":
            expired += 1
        if before_pinned and not notice.is_pinned:
            unpinned += 1

    if due:
        await db.commit()
    return {"scheduledPromoted": promoted, "expiredCount": expired, "unpinnedCount": unpinned}


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def target_to_dict(target: NoticeTarget) -> Dict[str, Any]:
    return {
        "id": str(target.id),
        "noticeId": str(target.notice_id),
        "targetType": target.target_type,
        "buildingId": str(target.building_id) if target.building_id else None,
        "wingId": str(target.wing_id) if target.wing_id else None,
        "flatId": str(target.flat_id) if target.flat_id else None,
        "residentId": str(target.resident_id) if target.resident_id else None,
        "committeeRole": target.committee_role,
        "isActive": target.is_active,
    }


def attachment_to_dict(att: NoticeAttachment) -> Dict[str, Any]:
    return {
        "id": str(att.id),
        "noticeId": str(att.notice_id),
        "fileName": att.file_name,
        "fileUrl": att.file_url,
        "mimeType": att.mime_type,
        "fileSizeBytes": att.file_size_bytes,
        "sortOrder": att.sort_order,
        "uploadedBy": str(att.uploaded_by) if att.uploaded_by else None,
        "createdAt": att.created_at.isoformat() if att.created_at else None,
    }


def notice_to_dict(
    notice: Notice,
    *,
    targets: Optional[Sequence[NoticeTarget]] = None,
    attachments: Optional[Sequence[NoticeAttachment]] = None,
    read_count: Optional[int] = None,
    ack_count: Optional[int] = None,
    audience_count: Optional[int] = None,
    is_read: Optional[bool] = None,
    is_acknowledged: Optional[bool] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": str(notice.id),
        "societyId": str(notice.society_id),
        "noticeNumber": notice.notice_number,
        "title": notice.title,
        "summary": notice.summary,
        "bodyText": notice.body_text,
        "bodyHtml": notice.body_html,
        "category": notice.category,
        "priority": notice.priority,
        "status": notice.status,
        "publishAt": notice.publish_at.isoformat() if notice.publish_at else None,
        "publishedAt": notice.published_at.isoformat() if notice.published_at else None,
        "expiresAt": notice.expires_at.isoformat() if notice.expires_at else None,
        "expiredAt": notice.expired_at.isoformat() if notice.expired_at else None,
        "archivedAt": notice.archived_at.isoformat() if notice.archived_at else None,
        "cancelledAt": notice.cancelled_at.isoformat() if notice.cancelled_at else None,
        "cancelReason": notice.cancel_reason,
        "isPinned": notice.is_pinned,
        "pinUntil": notice.pin_until.isoformat() if notice.pin_until else None,
        "requiresAcknowledgement": notice.requires_acknowledgement,
        "acknowledgementDueAt": (
            notice.acknowledgement_due_at.isoformat() if notice.acknowledgement_due_at else None
        ),
        "audienceCountSnapshot": notice.audience_count_snapshot,
        "publishedByUserId": str(notice.published_by_user_id) if notice.published_by_user_id else None,
        "metadata": notice.metadata_json or {},
        "notes": notice.notes,
        "isActive": notice.is_active,
        "version": notice.version,
        "createdAt": notice.created_at.isoformat() if notice.created_at else None,
        "updatedAt": notice.updated_at.isoformat() if notice.updated_at else None,
    }
    if targets is not None:
        data["targets"] = [target_to_dict(t) for t in targets]
    if attachments is not None:
        data["attachments"] = [attachment_to_dict(a) for a in attachments]
    if audience_count is not None:
        data["audienceCount"] = audience_count
    if read_count is not None:
        data["readCount"] = read_count
    if ack_count is not None:
        data["acknowledgementCount"] = ack_count
    if is_read is not None:
        data["isRead"] = is_read
    if is_acknowledged is not None:
        data["isAcknowledged"] = is_acknowledged
    return data
