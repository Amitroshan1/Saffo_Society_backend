"""Guard dashboard — stats, SOS, deliveries, staff-inside, recent activity.

Reads existing visits/complaints/flats. No new tables.
SOS is mapped from security/critical complaints.
Deliveries and household staff-inside are mapped from visits.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.complaint import Complaint
from Models.flat import Flat
from Models.visit import Visit
from Models.visitor import Visitor
from Models.wing import Wing
from Utils.audit import apply_update_audit, utcnow
from Utils.errors import ApiError

IST = timezone(timedelta(hours=5, minutes=30))

DELIVERY_TYPES = frozenset({"delivery", "courier"})
STAFF_VISIT_TYPES = frozenset({"maid", "driver", "technician"})
PENDING_APPROVAL_STATUSES = frozenset({"waiting"})
INSIDE_STATUS = "checked_in"
OPEN_DELIVERY_STATUSES = frozenset({"waiting", "approved", "checked_in"})
SOS_PRIORITIES = frozenset({"critical"})
SOS_CATEGORIES = frozenset({"security"})
CLOSED_COMPLAINT_STATUSES = frozenset({"resolved", "closed", "rejected"})


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _today_start_utc() -> datetime:
    now_ist = datetime.now(IST)
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_ist.astimezone(timezone.utc)


def _format_clock(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%I:%M %p")


def _flat_label(flat: Flat | None, wing: Wing | None) -> str | None:
    if not flat:
        return None
    if wing and wing.code:
        return f"{wing.code}-{flat.flat_no}"
    return flat.flat_no


def _title_role(visitor_type: str) -> str:
    return visitor_type.replace("_", " ").strip().title() or "Staff"


def _is_collected(visit: Visit) -> bool:
    meta = visit.metadata_json or {}
    if meta.get("collectedAt") or meta.get("collected"):
        return True
    return visit.status in {"checked_out", "cancelled", "rejected", "expired"}


def _is_sos_complaint(complaint: Complaint) -> bool:
    if not complaint.is_active:
        return False
    return complaint.priority in SOS_PRIORITIES or complaint.category in SOS_CATEGORIES


def _sos_responded_at(complaint: Complaint) -> str | None:
    meta = complaint.metadata_json or {}
    nested = meta.get("guardSos") if isinstance(meta.get("guardSos"), dict) else {}
    return nested.get("respondedAt") or meta.get("guardRespondedAt")


def _sos_status(complaint: Complaint) -> str:
    if _sos_responded_at(complaint) or complaint.status in CLOSED_COMPLAINT_STATUSES:
        return "responded"
    return "active"


def _visit_base(society_id: UUID) -> Select[tuple[Visit]]:
    return select(Visit).where(Visit.society_id == society_id, Visit.is_active.is_(True))


async def _count(db: AsyncSession, stmt: Select) -> int:
    counted = select(func.count()).select_from(stmt.subquery())
    return int((await db.execute(counted)).scalar_one() or 0)


async def _load_visit_maps(
    db: AsyncSession, visits: Iterable[Visit]
) -> tuple[dict[UUID, Visitor], dict[UUID, Flat], dict[UUID, Wing]]:
    visits = list(visits)
    visitor_ids = {v.visitor_id for v in visits}
    flat_ids = {v.flat_id for v in visits}
    wing_ids = {v.wing_id for v in visits}

    visitors: dict[UUID, Visitor] = {}
    if visitor_ids:
        visitors = {
            row.id: row
            for row in (await db.execute(select(Visitor).where(Visitor.id.in_(visitor_ids)))).scalars().all()
        }
    flats: dict[UUID, Flat] = {}
    if flat_ids:
        flats = {
            row.id: row
            for row in (await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))).scalars().all()
        }
    wings: dict[UUID, Wing] = {}
    if wing_ids:
        wings = {
            row.id: row
            for row in (await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))).scalars().all()
        }
    return visitors, flats, wings


async def _load_flat_maps(
    db: AsyncSession, complaints: Iterable[Complaint]
) -> tuple[dict[UUID, Flat], dict[UUID, Wing]]:
    complaints = list(complaints)
    flat_ids = {c.flat_id for c in complaints if c.flat_id}
    wing_ids = {c.wing_id for c in complaints if c.wing_id}
    flats: dict[UUID, Flat] = {}
    if flat_ids:
        flats = {
            row.id: row
            for row in (await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))).scalars().all()
        }
    wings: dict[UUID, Wing] = {}
    if wing_ids:
        wings = {
            row.id: row
            for row in (await db.execute(select(Wing).where(Wing.id.in_(wing_ids)))).scalars().all()
        }
    return flats, wings


def _company_name(visit: Visit) -> str:
    meta = visit.metadata_json or {}
    for key in ("company", "courier", "courierName"):
        value = meta.get(key)
        if value:
            return str(value)
    if visit.purpose:
        return visit.purpose
    return _title_role(visit.visitor_type)


def _delivery_status(visit: Visit) -> str:
    if visit.status == "checked_in":
        return "Inside"
    return "At Gate"


def _activity_type(visit: Visit) -> str:
    purpose = (visit.purpose or "").lower()
    if visit.status == "checked_out":
        return "exit"
    if visit.visitor_type in DELIVERY_TYPES:
        return "delivery"
    if visit.visitor_type in STAFF_VISIT_TYPES:
        return "staff"
    if "cab" in purpose or (visit.visitor_type == "other" and visit.vehicle_number):
        return "cab"
    return "visitor"


def _activity_message(visit: Visit, name: str, flat: str) -> str:
    kind = _activity_type(visit)
    if kind == "delivery":
        return f"Delivery by {name} for Flat {flat}"
    if kind == "exit":
        return f"Visitor {name} exited from Flat {flat}"
    if kind == "staff":
        return f"Staff {name} checked in for Flat {flat}"
    if kind == "cab":
        plate = visit.vehicle_number or name
        return f"Cab {plate} entered for Flat {flat}"
    if visit.status == "waiting":
        return f"Visitor {name} entry requested for Flat {flat}"
    return f"Visitor {name} entered Flat {flat}"


def _serialize_delivery(visit: Visit, visitor: Visitor | None, flat_label: str | None) -> dict[str, Any]:
    person = visitor.name if visitor else "Delivery"
    row_id = str(visit.id)
    return {
        "id": row_id,
        "_id": row_id,
        "person": person,
        "courier": person,
        "flat": flat_label,
        "company": _company_name(visit),
        "status": _delivery_status(visit),
        "arrivedTime": _format_clock(visit.expected_at or visit.check_in_time or visit.created_at),
        "package": (visit.metadata_json or {}).get("package") or "📦",
    }


def _serialize_staff(visit: Visit, visitor: Visitor | None, flat_label: str | None) -> dict[str, Any]:
    return {
        "id": str(visit.id),
        "name": visitor.name if visitor else "Staff",
        "role": _title_role(visit.visitor_type),
        "flat": flat_label,
        "since": _format_clock(visit.check_in_time or visit.created_at),
    }


def _serialize_sos(complaint: Complaint, flat_label: str | None) -> dict[str, Any]:
    row_id = str(complaint.id)
    return {
        "id": row_id,
        "_id": row_id,
        "flat": flat_label or "—",
        "time": _format_clock(complaint.created_at),
        "status": _sos_status(complaint),
        "note": complaint.title or complaint.description,
    }


def _serialize_activity(visit: Visit, visitor: Visitor | None, flat_label: str | None) -> dict[str, Any]:
    name = visitor.name if visitor else "Visitor"
    flat = flat_label or "—"
    stamp = visit.last_activity_at or visit.check_out_time or visit.check_in_time or visit.created_at
    return {
        "id": str(visit.id),
        "message": _activity_message(visit, name, flat),
        "time": _format_clock(stamp),
        "type": _activity_type(visit),
    }


async def get_dashboard_stats(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    start = _today_start_utc()

    total_entries_today = await _count(
        db,
        _visit_base(society_id).where(
            or_(Visit.check_in_time >= start, Visit.created_at >= start)
        ),
    )
    pending_approvals = await _count(
        db,
        _visit_base(society_id).where(Visit.status.in_(tuple(PENDING_APPROVAL_STATUSES))),
    )
    active_visitors = await _count(
        db,
        _visit_base(society_id).where(
            Visit.status == INSIDE_STATUS,
            Visit.visitor_type.notin_(tuple(DELIVERY_TYPES | STAFF_VISIT_TYPES)),
        ),
    )
    open_delivery_rows = (
        await db.execute(
            _visit_base(society_id).where(
                Visit.visitor_type.in_(tuple(DELIVERY_TYPES)),
                Visit.status.in_(tuple(OPEN_DELIVERY_STATUSES)),
            )
        )
    ).scalars().all()
    pending_deliveries = sum(1 for visit in open_delivery_rows if not _is_collected(visit))
    staff_inside = await _count(
        db,
        _visit_base(society_id).where(
            Visit.status == INSIDE_STATUS,
            Visit.visitor_type.in_(tuple(STAFF_VISIT_TYPES)),
        ),
    )

    sos_rows = (
        await db.execute(
            select(Complaint).where(
                Complaint.society_id == society_id,
                Complaint.is_active.is_(True),
                or_(
                    Complaint.priority.in_(tuple(SOS_PRIORITIES)),
                    Complaint.category.in_(tuple(SOS_CATEGORIES)),
                ),
            )
        )
    ).scalars().all()
    active_sos = sum(1 for row in sos_rows if _sos_status(row) == "active")

    return {
        "totalEntriesToday": total_entries_today,
        "pendingApprovalsCount": pending_approvals,
        "activeVisitorsCount": active_visitors,
        "deliveriesPendingCount": pending_deliveries,
        "staffInsideCount": staff_inside,
        "visitorsInsideCount": active_visitors,
        "todaysVisitorCount": total_entries_today,
        "pendingDeliveriesCount": pending_deliveries,
        "activeSosCount": active_sos,
    }


async def list_sos_alerts(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    rows = (
        await db.execute(
            select(Complaint)
            .where(
                Complaint.society_id == society_id,
                Complaint.is_active.is_(True),
                or_(
                    Complaint.priority.in_(tuple(SOS_PRIORITIES)),
                    Complaint.category.in_(tuple(SOS_CATEGORIES)),
                ),
            )
            .order_by(Complaint.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    flats, wings = await _load_flat_maps(db, rows)
    alerts = [
        _serialize_sos(row, _flat_label(flats.get(row.flat_id), wings.get(row.wing_id)))
        for row in rows
    ]
    alerts.sort(key=lambda item: (0 if item["status"] == "active" else 1, item["time"] or ""))
    return {"alerts": alerts}


async def respond_to_sos(
    db: AsyncSession,
    sos_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    complaint = (
        await db.execute(
            select(Complaint).where(Complaint.id == sos_id, Complaint.society_id == society_id)
        )
    ).scalar_one_or_none()
    if not complaint or not _is_sos_complaint(complaint):
        raise ApiError(404, "SOS alert not found")
    if _sos_status(complaint) == "responded":
        raise ApiError(409, "SOS already responded")

    now = utcnow()
    meta = dict(complaint.metadata_json or {})
    meta["guardRespondedAt"] = now.isoformat()
    meta["guardRespondedBy"] = str(actor_id)
    meta["guardSos"] = {
        "respondedAt": now.isoformat(),
        "respondedBy": str(actor_id),
    }
    complaint.metadata_json = meta
    apply_update_audit(complaint, actor_id)
    await db.commit()
    await db.refresh(complaint)

    flat = (
        await db.execute(select(Flat).where(Flat.id == complaint.flat_id))
    ).scalar_one_or_none()
    wing = (
        await db.execute(select(Wing).where(Wing.id == complaint.wing_id))
    ).scalar_one_or_none()
    return {"alert": _serialize_sos(complaint, _flat_label(flat, wing))}


async def list_pending_deliveries(
    db: AsyncSession,
    *,
    actor_society_id: UUID | None,
    collected: bool = False,
    limit: int = 20,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    stmt = _visit_base(society_id).where(Visit.visitor_type.in_(tuple(DELIVERY_TYPES)))
    if not collected:
        stmt = stmt.where(Visit.status.in_(tuple(OPEN_DELIVERY_STATUSES)))
    rows = (
        await db.execute(stmt.order_by(Visit.created_at.desc()).limit(min(limit, 100)))
    ).scalars().all()
    if collected:
        rows = [visit for visit in rows if _is_collected(visit)]
    else:
        rows = [visit for visit in rows if not _is_collected(visit)]

    visitors, flats, wings = await _load_visit_maps(db, rows)
    deliveries = [
        _serialize_delivery(
            visit,
            visitors.get(visit.visitor_id),
            _flat_label(flats.get(visit.flat_id), wings.get(visit.wing_id)),
        )
        for visit in rows
    ]
    return {"deliveries": deliveries}


async def collect_delivery(
    db: AsyncSession,
    visit_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = (
        await db.execute(
            select(Visit).where(Visit.id == visit_id, Visit.society_id == society_id)
        )
    ).scalar_one_or_none()
    if not visit or visit.visitor_type not in DELIVERY_TYPES:
        raise ApiError(404, "Delivery not found")
    if _is_collected(visit):
        raise ApiError(409, "Delivery already collected")

    now = utcnow()
    meta = dict(visit.metadata_json or {})
    meta["collected"] = True
    meta["collectedAt"] = now.isoformat()
    meta["collectedBy"] = str(actor_id)
    visit.metadata_json = meta
    if visit.status == "checked_in":
        visit.status = "checked_out"
        visit.check_out_time = now
        visit.gate_out_by = actor_id
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)

    visitors, flats, wings = await _load_visit_maps(db, [visit])
    return {
        "delivery": _serialize_delivery(
            visit,
            visitors.get(visit.visitor_id),
            _flat_label(flats.get(visit.flat_id), wings.get(visit.wing_id)),
        )
    }


async def list_staff_inside(
    db: AsyncSession, *, actor_society_id: UUID | None, limit: int = 20
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    rows = (
        await db.execute(
            _visit_base(society_id)
            .where(
                Visit.status == INSIDE_STATUS,
                Visit.visitor_type.in_(tuple(STAFF_VISIT_TYPES)),
            )
            .order_by(Visit.check_in_time.desc().nullslast(), Visit.created_at.desc())
            .limit(min(limit, 100))
        )
    ).scalars().all()
    visitors, flats, wings = await _load_visit_maps(db, rows)
    staff = [
        _serialize_staff(
            visit,
            visitors.get(visit.visitor_id),
            _flat_label(flats.get(visit.flat_id), wings.get(visit.wing_id)),
        )
        for visit in rows
    ]
    return {"staff": staff, "insideCount": len(staff)}


async def list_recent_activity(
    db: AsyncSession, *, actor_society_id: UUID | None, limit: int = 20
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    rows = (
        await db.execute(
            _visit_base(society_id)
            .order_by(
                Visit.last_activity_at.desc().nullslast(),
                Visit.created_at.desc(),
            )
            .limit(min(limit, 100))
        )
    ).scalars().all()
    visitors, flats, wings = await _load_visit_maps(db, rows)
    activities = [
        _serialize_activity(
            visit,
            visitors.get(visit.visitor_id),
            _flat_label(flats.get(visit.flat_id), wings.get(visit.wing_id)),
        )
        for visit in rows
    ]
    return {"activities": activities}
