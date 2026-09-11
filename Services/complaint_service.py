"""Complaint business logic — create through close/reopen lifecycle."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.building import Building
from Models.complaint import Complaint, ComplaintAttachment, ComplaintComment
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.staff import Staff
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.complaint import (
    ComplaintAssign,
    ComplaintAttachmentIn,
    ComplaintAttachmentOut,
    ComplaintCommentCreate,
    ComplaintCommentOut,
    ComplaintCreate,
    ComplaintListQueryParams,
    ComplaintOut,
    ComplaintPriorityUpdate,
    ComplaintStatusUpdate,
    ComplaintUpdate,
)
from Services.complaint_helpers import (
    get_complaint_in_society,
    get_occupancy_in_society,
    get_resident_in_society,
    get_staff_for_user,
    get_staff_in_society,
    resolve_resident_context,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

TERMINAL_FOR_RESIDENT_EDIT = {"closed", "rejected"}
RESOLVED_OR_CLOSED = {"resolved", "closed"}
SOS_PRIORITIES = frozenset({"critical"})
SOS_CATEGORIES = frozenset({"security"})


def _is_sos_complaint(complaint: Complaint) -> bool:
    return complaint.priority in SOS_PRIORITIES or complaint.category in SOS_CATEGORIES


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _comment_out(comment: ComplaintComment, author_name: Optional[str] = None) -> dict:
    return ComplaintCommentOut(
        id=comment.id,
        complaintId=comment.complaint_id,
        authorType=comment.author_type,
        authorId=comment.author_id,
        authorName=author_name,
        message=comment.message,
        createdAt=comment.created_at,
        createdBy=comment.created_by,
    ).model_dump(mode="json")


def _attachment_out(att: ComplaintAttachment) -> dict:
    return ComplaintAttachmentOut(
        id=att.id,
        complaintId=att.complaint_id,
        fileName=att.file_name,
        fileUrl=att.file_url,
        mimeType=att.mime_type,
        uploadedBy=att.uploaded_by,
        createdAt=att.created_at,
    ).model_dump(mode="json")


async def _load_context_maps(
    db: AsyncSession, complaints: list[Complaint]
) -> tuple[dict, dict, dict, dict, dict]:
    resident_ids = {c.resident_id for c in complaints}
    flat_ids = {c.flat_id for c in complaints}
    wing_ids = {c.wing_id for c in complaints}
    building_ids = {c.building_id for c in complaints}
    staff_ids = {c.assigned_staff_id for c in complaints if c.assigned_staff_id}

    residents = {}
    if resident_ids:
        r = await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
        residents = {x.id: x for x in r.scalars().all()}
    flats = {}
    if flat_ids:
        r = await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
        flats = {x.id: x for x in r.scalars().all()}
    wings = {}
    if wing_ids:
        r = await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))
        wings = {x.id: x for x in r.scalars().all()}
    buildings = {}
    if building_ids:
        r = await db.execute(select(Building).where(Building.id.in_(building_ids)))
        buildings = {x.id: x for x in r.scalars().all()}
    staff = {}
    if staff_ids:
        r = await db.execute(select(Staff).where(Staff.id.in_(staff_ids)))
        staff = {x.id: x for x in r.scalars().all()}
    return residents, flats, wings, buildings, staff


async def _load_comments_attachments(
    db: AsyncSession, complaint_ids: list[UUID]
) -> tuple[dict[UUID, list], dict[UUID, list]]:
    comments_map: dict[UUID, list] = {cid: [] for cid in complaint_ids}
    attachments_map: dict[UUID, list] = {cid: [] for cid in complaint_ids}
    if not complaint_ids:
        return comments_map, attachments_map

    comments = (
        await db.execute(
            select(ComplaintComment)
            .where(
                ComplaintComment.complaint_id.in_(complaint_ids),
                ComplaintComment.is_active.is_(True),
            )
            .order_by(ComplaintComment.created_at.asc())
        )
    ).scalars().all()
    for c in comments:
        comments_map.setdefault(c.complaint_id, []).append(c)

    attachments = (
        await db.execute(
            select(ComplaintAttachment)
            .where(
                ComplaintAttachment.complaint_id.in_(complaint_ids),
                ComplaintAttachment.is_active.is_(True),
            )
            .order_by(ComplaintAttachment.created_at.asc())
        )
    ).scalars().all()
    for a in attachments:
        attachments_map.setdefault(a.complaint_id, []).append(a)
    return comments_map, attachments_map


def _complaint_dict(
    complaint: Complaint,
    *,
    resident: Optional[Resident] = None,
    flat: Optional[Flat] = None,
    wing: Optional[Wing] = None,
    building: Optional[Building] = None,
    staff: Optional[Staff] = None,
    comments: Optional[list] = None,
    attachments: Optional[list] = None,
) -> Dict[str, Any]:
    comment_outs = None
    if comments is not None:
        comment_outs = [
            ComplaintCommentOut(
                id=c.id,
                complaintId=c.complaint_id,
                authorType=c.author_type,
                authorId=c.author_id,
                message=c.message,
                createdAt=c.created_at,
                createdBy=c.created_by,
            )
            for c in comments
        ]
    attachment_outs = None
    if attachments is not None:
        attachment_outs = [
            ComplaintAttachmentOut(
                id=a.id,
                complaintId=a.complaint_id,
                fileName=a.file_name,
                fileUrl=a.file_url,
                mimeType=a.mime_type,
                uploadedBy=a.uploaded_by,
                createdAt=a.created_at,
            )
            for a in attachments
        ]
    return ComplaintOut.from_orm_complaint(
        complaint,
        resident_name=resident.name if resident else None,
        resident_code=resident.code if resident else None,
        flat_no=flat.flat_no if flat else None,
        wing_code=wing.code if wing else None,
        building_name=building.name if building else None,
        assigned_staff_name=staff.name if staff else None,
        comments=comment_outs,
        attachments=attachment_outs,
    ).model_dump(mode="json")


async def _add_attachments(
    db: AsyncSession,
    complaint: Complaint,
    attachments: List[ComplaintAttachmentIn],
    *,
    actor_id: UUID,
) -> None:
    for item in attachments:
        att = ComplaintAttachment(
            complaint_id=complaint.id,
            file_name=item.fileName,
            file_url=item.fileUrl,
            mime_type=item.mimeType,
            uploaded_by=actor_id,
            is_active=True,
            version=1,
        )
        apply_create_audit(att, actor_id)
        db.add(att)


async def create_complaint(
    db: AsyncSession,
    body: ComplaintCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)

    if actor_role == "resident":
        resident, occupancy = await resolve_resident_context(
            db, actor_id=actor_id, society_id=society_id
        )
        source = "resident"
    else:
        if not body.occupancyId and not (body.residentId and body.flatId):
            raise ApiError(422, "occupancyId or residentId+flatId is required")
        if body.occupancyId:
            occupancy = await get_occupancy_in_society(db, body.occupancyId, society_id)
        else:
            occupancy = (
                await db.execute(
                    select(Occupancy).where(
                        Occupancy.society_id == society_id,
                        Occupancy.resident_id == body.residentId,
                        Occupancy.flat_id == body.flatId,
                        Occupancy.status == "active",
                    )
                )
            ).scalar_one_or_none()
            if not occupancy:
                raise ApiError(404, "Active occupancy not found")
        resident = await get_resident_in_society(db, occupancy.resident_id, society_id)
        source = body.source if body.source else "admin"

    if occupancy.status != "active":
        raise ApiError(422, "Occupancy must be active")

    complaint = Complaint(
        society_id=society_id,
        building_id=occupancy.building_id,
        wing_id=occupancy.wing_id,
        flat_id=occupancy.flat_id,
        occupancy_id=occupancy.id,
        resident_id=resident.id,
        category=body.category,
        subcategory=body.subcategory,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status="open",
        source=source,
        expected_resolution=body.expectedResolution,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(complaint, actor_id)
    db.add(complaint)
    await db.flush()
    await _add_attachments(db, complaint, body.attachments, actor_id=actor_id)
    await db.commit()
    await db.refresh(complaint)

    complaint_payload = {
        "status": complaint.status,
        "priority": complaint.priority,
        "category": complaint.category,
        "complaint_title": complaint.title,
    }
    publish_simple(
        "ComplaintCreated",
        society_id=society_id,
        entity_type="complaint",
        entity_id=complaint.id,
        actor_id=actor_id,
        payload=complaint_payload,
    )
    if _is_sos_complaint(complaint):
        publish_simple(
            "SosAlertCreated",
            society_id=society_id,
            entity_type="complaint",
            entity_id=complaint.id,
            actor_id=actor_id,
            payload=complaint_payload,
        )
    return await get_complaint(
        db, complaint.id, actor_society_id=society_id, include_details=True
    )


async def list_complaints(
    db: AsyncSession,
    query: ComplaintListQueryParams,
    *,
    actor_society_id: UUID | None,
    resident_id: UUID | None = None,
    assigned_staff_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(Complaint).where(Complaint.society_id == society_id)

    if resident_id:
        base = base.where(Complaint.resident_id == resident_id)
    if assigned_staff_id:
        base = base.where(Complaint.assigned_staff_id == assigned_staff_id)
    if query.building_id:
        base = base.where(Complaint.building_id == query.building_id)
    if query.wing_id:
        base = base.where(Complaint.wing_id == query.wing_id)
    if query.flat_id:
        base = base.where(Complaint.flat_id == query.flat_id)
    if query.resident_id:
        base = base.where(Complaint.resident_id == query.resident_id)
    if query.assigned_staff_id:
        base = base.where(Complaint.assigned_staff_id == query.assigned_staff_id)
    if query.status:
        base = base.where(Complaint.status == query.status)
    if query.priority:
        base = base.where(Complaint.priority == query.priority)
    if query.category:
        base = base.where(Complaint.category == query.category)
    if query.source:
        base = base.where(Complaint.source == query.source)
    if query.is_active is not None:
        base = base.where(Complaint.is_active == query.is_active)

    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                Complaint.title.ilike(term),
                Complaint.description.ilike(term),
                Complaint.category.ilike(term),
            )
        )

    allowed_sort = ("created_at", "priority", "status", "title", "updated_at")
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Complaint, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()
    complaints = list(rows)
    residents, flats, wings, buildings, staff = await _load_context_maps(db, complaints)
    return {
        "complaints": [
            _complaint_dict(
                c,
                resident=residents.get(c.resident_id),
                flat=flats.get(c.flat_id),
                wing=wings.get(c.wing_id),
                building=buildings.get(c.building_id),
                staff=staff.get(c.assigned_staff_id) if c.assigned_staff_id else None,
            )
            for c in complaints
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    *,
    actor_society_id: UUID | None,
    include_details: bool = True,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    residents, flats, wings, buildings, staff = await _load_context_maps(db, [complaint])
    comments = None
    attachments = None
    if include_details:
        comments_map, attachments_map = await _load_comments_attachments(db, [complaint.id])
        comments = comments_map.get(complaint.id, [])
        attachments = attachments_map.get(complaint.id, [])
    return {
        "complaint": _complaint_dict(
            complaint,
            resident=residents.get(complaint.resident_id),
            flat=flats.get(complaint.flat_id),
            wing=wings.get(complaint.wing_id),
            building=buildings.get(complaint.building_id),
            staff=staff.get(complaint.assigned_staff_id) if complaint.assigned_staff_id else None,
            comments=comments,
            attachments=attachments,
        )
    }


async def update_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    if complaint.status in TERMINAL_FOR_RESIDENT_EDIT:
        raise ApiError(422, f"Complaint is {complaint.status} and cannot be updated")

    data = body.model_dump(exclude_unset=True)
    field_map = {
        "category": "category",
        "subcategory": "subcategory",
        "title": "title",
        "description": "description",
        "expectedResolution": "expected_resolution",
        "notes": "notes",
        "metadata": "metadata_json",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(complaint, orm_key, data[api_key])
    apply_update_audit(complaint, actor_id)
    await db.commit()
    await db.refresh(complaint)
    return await get_complaint(db, complaint.id, actor_society_id=society_id)


async def assign_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintAssign,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    if complaint.status in {"closed", "rejected"}:
        raise ApiError(422, "Cannot assign a closed or rejected complaint")

    staff = await get_staff_in_society(db, body.staffId, society_id)
    if not staff.is_active:
        raise ApiError(422, "Staff member is inactive")

    complaint.assigned_staff_id = staff.id
    if complaint.status in {"open", "reopened"}:
        complaint.status = "assigned"
    if body.notes:
        complaint.notes = body.notes
    apply_update_audit(complaint, actor_id)
    await db.commit()
    await db.refresh(complaint)

    publish_simple(
        "ComplaintAssigned",
        society_id=society_id,
        entity_type="complaint",
        entity_id=complaint.id,
        actor_id=actor_id,
        payload={
            "assignedStaffId": str(staff.id),
            "status": complaint.status,
            "complaint_title": complaint.title,
        },
    )
    publish_simple(
        "ComplaintStatusChanged",
        society_id=society_id,
        entity_type="complaint",
        entity_id=complaint.id,
        actor_id=actor_id,
        payload={"status": complaint.status},
    )
    return await get_complaint(db, complaint.id, actor_society_id=society_id)


async def update_status(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintStatusUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    old_status = complaint.status
    complaint.status = body.status
    if body.status == "resolved" and not complaint.resolved_at:
        complaint.resolved_at = utcnow()
    if body.status == "closed" and not complaint.closed_at:
        complaint.closed_at = utcnow()
        complaint.is_active = False
    if body.status == "reopened":
        complaint.closed_at = None
        complaint.resolved_at = None
        complaint.is_active = True
    if body.notes:
        complaint.notes = body.notes
    apply_update_audit(complaint, actor_id)
    await db.commit()
    await db.refresh(complaint)

    publish_simple(
        "ComplaintStatusChanged",
        society_id=society_id,
        entity_type="complaint",
        entity_id=complaint.id,
        actor_id=actor_id,
        payload={"from": old_status, "to": complaint.status},
    )
    if body.status == "resolved":
        publish_simple(
            "ComplaintResolved",
            society_id=society_id,
            entity_type="complaint",
            entity_id=complaint.id,
            actor_id=actor_id,
        )
    if body.status == "closed":
        publish_simple(
            "ComplaintClosed",
            society_id=society_id,
            entity_type="complaint",
            entity_id=complaint.id,
            actor_id=actor_id,
        )
    if body.status == "reopened":
        publish_simple(
            "ComplaintReopened",
            society_id=society_id,
            entity_type="complaint",
            entity_id=complaint.id,
            actor_id=actor_id,
        )
    return await get_complaint(db, complaint.id, actor_society_id=society_id)


async def update_priority(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintPriorityUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    complaint.priority = body.priority
    if body.notes:
        complaint.notes = body.notes
    apply_update_audit(complaint, actor_id)
    await db.commit()
    await db.refresh(complaint)
    return await get_complaint(db, complaint.id, actor_society_id=society_id)


async def add_comment(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintCommentCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)

    author_type = actor_role
    if actor_role == "guard":
        staff = await get_staff_for_user(db, actor_id, society_id)
        author_type = "staff" if staff else "guard"
    elif actor_role == "admin":
        author_type = "admin"
    elif actor_role == "resident":
        author_type = "resident"

    comment = ComplaintComment(
        complaint_id=complaint.id,
        author_type=author_type,
        author_id=actor_id,
        message=body.message,
        is_active=True,
        version=1,
    )
    apply_create_audit(comment, actor_id)
    apply_update_audit(complaint, actor_id)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    publish_simple(
        "ComplaintCommentAdded",
        society_id=society_id,
        entity_type="complaint",
        entity_id=complaint.id,
        actor_id=actor_id,
        payload={"commentId": str(comment.id)},
    )
    return {
        "comment": _comment_out(comment),
        "complaint": (await get_complaint(db, complaint.id, actor_society_id=society_id))[
            "complaint"
        ],
    }


async def resolve_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    payload = body or ComplaintStatusUpdate(status="resolved")
    payload.status = "resolved"
    return await update_status(
        db, complaint_id, payload, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def reopen_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    if complaint.status not in RESOLVED_OR_CLOSED and complaint.status != "rejected":
        raise ApiError(422, "Only resolved, closed, or rejected complaints can be reopened")
    payload = body or ComplaintStatusUpdate(status="reopened")
    payload.status = "reopened"
    return await update_status(
        db, complaint_id, payload, actor_id=actor_id, actor_society_id=society_id
    )


async def close_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    body: ComplaintStatusUpdate | None,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
    resident_id: UUID | None = None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)

    if actor_role == "resident":
        if resident_id and complaint.resident_id != resident_id:
            raise ApiError(404, "Complaint not found")
        if complaint.status != "resolved":
            raise ApiError(422, "Residents can close complaints only after resolution")
    elif complaint.status not in {"resolved", "rejected", "open", "assigned", "in_progress", "waiting", "reopened"}:
        raise ApiError(422, "Complaint cannot be closed in current status")

    payload = body or ComplaintStatusUpdate(status="closed")
    payload.status = "closed"
    return await update_status(
        db, complaint_id, payload, actor_id=actor_id, actor_society_id=society_id
    )


async def dashboard_stats(
    db: AsyncSession, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(Complaint).where(Complaint.society_id == society_id)

    total = int(
        (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    )
    by_status = {}
    for status in (
        "open",
        "assigned",
        "in_progress",
        "waiting",
        "resolved",
        "closed",
        "reopened",
        "rejected",
    ):
        cnt = int(
            (
                await db.execute(
                    select(func.count()).where(
                        Complaint.society_id == society_id,
                        Complaint.status == status,
                    )
                )
            ).scalar_one()
        )
        by_status[status] = cnt

    by_priority = {}
    for priority in ("low", "medium", "high", "critical"):
        cnt = int(
            (
                await db.execute(
                    select(func.count()).where(
                        Complaint.society_id == society_id,
                        Complaint.priority == priority,
                        Complaint.status.notin_(["closed", "rejected"]),
                    )
                )
            ).scalar_one()
        )
        by_priority[priority] = cnt

    unassigned = int(
        (
            await db.execute(
                select(func.count()).where(
                    Complaint.society_id == society_id,
                    Complaint.assigned_staff_id.is_(None),
                    Complaint.status.in_(["open", "reopened"]),
                )
            )
        ).scalar_one()
    )

    return {
        "total": total,
        "byStatus": by_status,
        "byPriority": by_priority,
        "unassigned": unassigned,
        "openCount": by_status.get("open", 0) + by_status.get("reopened", 0),
        "inProgressCount": by_status.get("in_progress", 0) + by_status.get("assigned", 0),
        "resolvedCount": by_status.get("resolved", 0),
    }


async def assert_resident_owns_complaint(
    db: AsyncSession,
    complaint_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> tuple[Resident, Complaint]:
    society_id = _require_society_id(actor_society_id)
    resident, _ = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    complaint = await get_complaint_in_society(db, complaint_id, society_id)
    if complaint.resident_id != resident.id:
        raise ApiError(404, "Complaint not found")
    return resident, complaint


async def assert_staff_assigned_or_admin(
    db: AsyncSession,
    complaint: Complaint,
    *,
    actor_id: UUID,
    actor_role: str,
    actor_society_id: UUID,
) -> None:
    if actor_role == "admin":
        return
    staff = await get_staff_for_user(db, actor_id, actor_society_id)
    if not staff or complaint.assigned_staff_id != staff.id:
        raise ApiError(403, "Access denied for this complaint")
