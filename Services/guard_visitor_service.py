"""Guard walk-in visitors — create, list, approve, deny, exit, readd, OTP, flats."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.visit import Visit
from Models.visitor import Visitor
from Models.wing import Wing
from Schemas.common import build_pagination_meta
from Schemas.guard_visitor_schema import (
    GuardCallLogCreate,
    GuardOtpVerify,
    GuardVisitorCreate,
    GuardVisitorDecision,
    GuardVisitorListQueryParams,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError
from Utils.local_upload import save_visitor_photo, save_visitor_photo_from_payload

IST = timezone(timedelta(hours=5, minutes=30))

PURPOSE_TO_TYPE = {
    "guest": "guest",
    "work / service": "technician",
    "work": "technician",
    "service": "technician",
    "delivery": "delivery",
    "courier": "courier",
    "cab": "other",
    "medical": "other",
    "maid": "maid",
    "driver": "driver",
    "technician": "technician",
    "vendor": "vendor",
    "other": "other",
}

UI_STATUS_MAP = {
    "pending": ("waiting", "scheduled"),
    "approved": ("checked_in", "approved"),
    "rejected": ("rejected",),
    "inside": ("checked_in",),
    "exited": ("checked_out",),
}


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _format_clock(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%I:%M %p")


def _human_duration(start: datetime | None) -> str:
    if start is None:
        return "0m"
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    minutes = max(0, int((utcnow() - start).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def _flat_label(flat: Flat | None, wing: Wing | None) -> str | None:
    if not flat:
        return None
    if wing and wing.code:
        return f"{wing.code}-{flat.flat_no}"
    return flat.flat_no


def _visitor_type_from_purpose(purpose: str) -> str:
    key = purpose.strip().lower()
    return PURPOSE_TO_TYPE.get(key, "other")


def _ui_status(visit: Visit) -> str:
    if visit.status in {"waiting", "scheduled"}:
        return "pending"
    if visit.status in {"checked_in", "approved"}:
        return "approved"
    if visit.status == "rejected":
        return "rejected"
    if visit.status == "checked_out":
        return "exited"
    return visit.status


def _serialize(
    visit: Visit,
    visitor: Visitor | None,
    flat: Flat | None,
    wing: Wing | None,
    resident_name: str | None = None,
) -> Dict[str, Any]:
    meta = visit.metadata_json or {}
    stamp = visit.check_in_time or visit.created_at
    row_id = str(visit.id)
    return {
        "id": row_id,
        "_id": row_id,
        "visitId": row_id,
        "visitorId": str(visit.visitor_id),
        "name": visitor.name if visitor else None,
        "phone": visitor.phone if visitor else None,
        "flat": _flat_label(flat, wing),
        "flatId": str(visit.flat_id),
        "purpose": visit.purpose,
        "persons": visit.number_of_people,
        "time": _format_clock(stamp),
        "wait": _human_duration(visit.created_at) if visit.status in {"waiting", "scheduled"} else None,
        "duration": _human_duration(visit.check_in_time) if visit.status == "checked_in" else None,
        "by": meta.get("rejectedBy"),
        "vehicle": visit.vehicle_number or "",
        "vehicleType": meta.get("vehicleType"),
        "photoUrl": visitor.photo_url if visitor else None,
        "photo_url": visitor.photo_url if visitor else None,
        "status": _ui_status(visit),
        "notifyResident": bool(meta.get("notifyResident", True)),
        "preApproved": visit.is_preapproved,
        "remarks": visit.notes,
        "residentName": resident_name,
        "createdAt": visit.created_at.isoformat() if visit.created_at else None,
        "checkInTime": visit.check_in_time.isoformat() if visit.check_in_time else None,
    }


async def _load_maps(
    db: AsyncSession, visits: list[Visit]
) -> tuple[dict[UUID, Visitor], dict[UUID, Flat], dict[UUID, Wing], dict[UUID, str]]:
    visitor_ids = {v.visitor_id for v in visits}
    flat_ids = {v.flat_id for v in visits}
    wing_ids = {v.wing_id for v in visits}
    occupancy_ids = {v.occupancy_id for v in visits}

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
    resident_names: dict[UUID, str] = {}
    if occupancy_ids:
        occs = {
            row.id: row
            for row in (
                await db.execute(select(Occupancy).where(Occupancy.id.in_(occupancy_ids)))
            ).scalars().all()
        }
        resident_ids = {o.resident_id for o in occs.values()}
        residents = {}
        if resident_ids:
            residents = {
                row.id: row
                for row in (
                    await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
                ).scalars().all()
            }
        for occ_id, occ in occs.items():
            resident = residents.get(occ.resident_id)
            if resident:
                resident_names[occ_id] = resident.name
    return visitors, flats, wings, resident_names


async def _get_visit(db: AsyncSession, visit_id: UUID, society_id: UUID) -> Visit:
    visit = (
        await db.execute(
            select(Visit).where(Visit.id == visit_id, Visit.society_id == society_id)
        )
    ).scalar_one_or_none()
    if not visit:
        raise ApiError(404, "Visitor entry not found")
    return visit


async def _serialize_one(db: AsyncSession, visit: Visit) -> Dict[str, Any]:
    visitors, flats, wings, names = await _load_maps(db, [visit])
    return _serialize(
        visit,
        visitors.get(visit.visitor_id),
        flats.get(visit.flat_id),
        wings.get(visit.wing_id),
        names.get(visit.occupancy_id),
    )


async def _resolve_occupancy(
    db: AsyncSession,
    *,
    society_id: UUID,
    occupancy_id: UUID | None,
    flat_id: UUID | None,
    flat_label: str | None,
) -> Occupancy:
    if occupancy_id:
        occ = (
            await db.execute(
                select(Occupancy).where(
                    Occupancy.id == occupancy_id,
                    Occupancy.society_id == society_id,
                )
            )
        ).scalar_one_or_none()
        if not occ:
            raise ApiError(404, "Occupancy not found")
        if occ.status != "active" or not occ.is_active:
            raise ApiError(422, "Occupancy must be active")
        return occ

    resolved_flat_id = flat_id
    if not resolved_flat_id and flat_label:
        resolved_flat_id = await _find_flat_id(db, society_id, flat_label)
    if not resolved_flat_id:
        raise ApiError(422, "flat, flatId, or occupancyId is required")

    occ = (
        await db.execute(
            select(Occupancy)
            .where(
                Occupancy.society_id == society_id,
                Occupancy.flat_id == resolved_flat_id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
            .order_by(Occupancy.is_primary.desc(), Occupancy.move_in_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not occ:
        raise ApiError(422, "No active resident found for this flat")
    return occ


async def _find_flat_id(db: AsyncSession, society_id: UUID, raw: str) -> UUID:
    label = raw.strip()
    if not label:
        raise ApiError(422, "Flat is required")

    wing_code = None
    flat_no = label
    if "-" in label:
        wing_code, flat_no = label.split("-", 1)
        wing_code, flat_no = wing_code.strip(), flat_no.strip()

    stmt = (
        select(Flat)
        .join(Wing, Wing.id == Flat.wing_id)
        .where(Flat.society_id == society_id, Flat.is_active.is_(True))
    )
    if wing_code:
        stmt = stmt.where(
            or_(Wing.code.ilike(wing_code), Wing.code.ilike(f"{wing_code}%")),
            Flat.flat_no.ilike(flat_no),
        )
    else:
        stmt = stmt.where(or_(Flat.flat_no.ilike(flat_no), Flat.flat_no.ilike(f"%{flat_no}%")))

    rows = (await db.execute(stmt.limit(5))).scalars().all()
    if not rows:
        raise ApiError(404, f"Flat '{label}' not found")
    if len(rows) > 1 and not wing_code:
        raise ApiError(422, f"Multiple flats match '{label}'. Use wing-flat, e.g. A1-101")
    return rows[0].id


async def _get_or_create_visitor(
    db: AsyncSession,
    *,
    society_id: UUID,
    actor_id: UUID,
    name: str,
    phone: str,
    photo_url: str | None,
) -> Visitor:
    existing = (
        await db.execute(
            select(Visitor).where(
                Visitor.society_id == society_id,
                Visitor.phone == phone,
                Visitor.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.name = name
        if photo_url:
            existing.photo_url = photo_url
        apply_update_audit(existing, actor_id)
        return existing

    visitor = Visitor(
        society_id=society_id,
        name=name,
        phone=phone,
        photo_url=photo_url,
        metadata_json={},
        is_active=True,
        version=1,
    )
    apply_create_audit(visitor, actor_id)
    db.add(visitor)
    await db.flush()
    return visitor


async def create_walk_in(
    db: AsyncSession,
    body: GuardVisitorCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    photo_bytes: bytes | None = None,
    photo_filename: str | None = None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    occupancy = await _resolve_occupancy(
        db,
        society_id=society_id,
        occupancy_id=body.occupancyId,
        flat_id=body.flatId,
        flat_label=body.flat,
    )

    photo_url = None
    if photo_bytes:
        photo_url = save_visitor_photo(
            society_id=society_id, data=photo_bytes, filename=photo_filename
        )
    else:
        photo_url = save_visitor_photo_from_payload(
            society_id, body.photo or body.photoUrl
        )

    visitor = await _get_or_create_visitor(
        db,
        society_id=society_id,
        actor_id=actor_id,
        name=body.name,
        phone=body.phone,
        photo_url=photo_url,
    )

    visitor_type = _visitor_type_from_purpose(body.purpose)
    now = utcnow()
    is_preapproved = body.preApproved
    status = "checked_in" if is_preapproved else "waiting"
    otp = f"{secrets.randbelow(1_000_000):06d}" if body.notifyResident and not is_preapproved else None

    meta: Dict[str, Any] = {
        "notifyResident": body.notifyResident,
        "source": "guard_walk_in",
    }
    if body.vehicleType:
        meta["vehicleType"] = body.vehicleType

    visit = Visit(
        society_id=society_id,
        building_id=occupancy.building_id,
        wing_id=occupancy.wing_id,
        flat_id=occupancy.flat_id,
        occupancy_id=occupancy.id,
        visitor_id=visitor.id,
        purpose=body.purpose,
        visitor_type=visitor_type,
        pass_type="delivery" if visitor_type in {"delivery", "courier"} else "one_time",
        status=status,
        expected_at=now,
        check_in_time=now if is_preapproved else None,
        approved_by=actor_id if is_preapproved else None,
        gate_in_by=actor_id if is_preapproved else None,
        vehicle_number=body.vehicle,
        number_of_people=body.persons,
        otp=otp,
        is_preapproved=is_preapproved,
        metadata_json=meta,
        notes=body.remarks,
        is_active=True,
        version=1,
    )
    apply_create_audit(visit, actor_id)
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    await db.refresh(visitor)

    publish_simple(
        "VisitCreated",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={"visitId": str(visit.id), "notifyResident": body.notifyResident},
    )
    row = await _serialize_one(db, visit)
    return {"visitor": row}


async def list_walk_ins(
    db: AsyncSession,
    query: GuardVisitorListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    base = select(Visit).where(Visit.society_id == society_id)
    statuses = UI_STATUS_MAP.get((query.status or "").lower())
    if statuses:
        base = base.where(Visit.status.in_(statuses))
    if query.purpose:
        base = base.where(Visit.purpose.ilike(query.purpose.strip()))

    if query.search:
        term = f"%{query.search.strip()}%"
        visitor_ids = select(Visitor.id).where(
            Visitor.society_id == society_id,
            or_(Visitor.name.ilike(term), Visitor.phone.ilike(term)),
        )
        flat_ids = (
            select(Flat.id)
            .join(Wing, Wing.id == Flat.wing_id)
            .where(
                Flat.society_id == society_id,
                or_(
                    Flat.flat_no.ilike(term),
                    Wing.code.ilike(term),
                    func.concat(Wing.code, "-", Flat.flat_no).ilike(term),
                ),
            )
        )
        base = base.where(
            or_(
                Visit.visitor_id.in_(visitor_ids),
                Visit.vehicle_number.ilike(term),
                Visit.flat_id.in_(flat_ids),
                Visit.purpose.ilike(term),
            )
        )

    base = base.order_by(Visit.created_at.desc())
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list(
        (
            await db.execute(
                base.offset((query.page - 1) * query.page_size).limit(query.page_size)
            )
        )
        .scalars()
        .all()
    )
    visitors, flats, wings, names = await _load_maps(db, rows)
    items = [
        _serialize(
            visit,
            visitors.get(visit.visitor_id),
            flats.get(visit.flat_id),
            wings.get(visit.wing_id),
            names.get(visit.occupancy_id),
        )
        for visit in rows
    ]
    return {
        "visitors": items,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_walk_in(
    db: AsyncSession, visit_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    return {"visitor": await _serialize_one(db, visit)}


async def approve_walk_in(
    db: AsyncSession,
    visit_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    if visit.status in {"checked_in", "checked_out"}:
        raise ApiError(409, "Visitor already approved or exited")
    if visit.status not in {"waiting", "scheduled", "approved"}:
        raise ApiError(422, "Only pending visitors can be approved")

    now = utcnow()
    visit.status = "checked_in"
    visit.approved_by = actor_id
    visit.gate_in_by = actor_id
    visit.check_in_time = now
    visit.is_active = True
    visit.otp = None
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    publish_simple(
        "VisitApproved",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={"visitId": str(visit.id)},
    )
    return {"visitor": await _serialize_one(db, visit)}


async def deny_walk_in(
    db: AsyncSession,
    visit_id: UUID,
    body: GuardVisitorDecision,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    if visit.status not in {"waiting", "scheduled", "approved"}:
        raise ApiError(422, "Visitor cannot be denied in current status")
    meta = dict(visit.metadata_json or {})
    meta["rejectedBy"] = (body.rejectedBy or "Guard").strip() or "Guard"
    meta["rejectedAt"] = utcnow().isoformat()
    visit.metadata_json = meta
    visit.status = "rejected"
    visit.is_active = False
    visit.otp = None
    if body.notes:
        visit.notes = body.notes
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    publish_simple(
        "VisitRejected",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={"visitId": str(visit.id)},
    )
    return {"visitor": await _serialize_one(db, visit)}


async def exit_walk_in(
    db: AsyncSession,
    visit_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    if visit.status == "checked_out":
        raise ApiError(409, "Visitor already exited")
    if visit.status != "checked_in":
        raise ApiError(422, "Visitor must be inside before marking exit")
    now = utcnow()
    visit.status = "checked_out"
    visit.check_out_time = now
    visit.gate_out_by = actor_id
    visit.is_active = False
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    publish_simple(
        "VisitCheckedOut",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={"visitId": str(visit.id)},
    )
    return {"visitor": await _serialize_one(db, visit)}


async def readd_walk_in(
    db: AsyncSession,
    visit_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    if visit.status != "rejected":
        raise ApiError(422, "Only rejected visitors can be moved back to pending")
    meta = dict(visit.metadata_json or {})
    meta.pop("rejectedBy", None)
    meta.pop("rejectedAt", None)
    visit.metadata_json = meta
    visit.status = "waiting"
    visit.is_active = True
    visit.otp = f"{secrets.randbelow(1_000_000):06d}"
    apply_update_audit(visit, actor_id)
    await db.commit()
    await db.refresh(visit)
    publish_simple(
        "VisitRequeued",
        society_id=society_id,
        entity_type="visit",
        entity_id=visit.id,
        actor_id=actor_id,
        payload={"visitId": str(visit.id)},
    )
    return {"visitor": await _serialize_one(db, visit)}


async def verify_otp(
    db: AsyncSession,
    visit_id: UUID,
    body: GuardOtpVerify,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, visit_id, society_id)
    if not visit.otp or visit.otp != body.otp.strip():
        raise ApiError(422, "Invalid OTP")
    return await approve_walk_in(
        db, visit_id, actor_id=actor_id, actor_society_id=society_id
    ) | {"verified": True}


async def recent_walk_ins(
    db: AsyncSession, *, actor_id: UUID, actor_society_id: UUID | None, limit: int = 5
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    rows = list(
        (
            await db.execute(
                select(Visit)
                .where(Visit.society_id == society_id, Visit.created_by == actor_id)
                .order_by(Visit.created_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    seen: set[UUID] = set()
    unique: list[Visit] = []
    for visit in rows:
        if visit.visitor_id in seen:
            continue
        seen.add(visit.visitor_id)
        unique.append(visit)
        if len(unique) >= limit:
            break
    visitors, flats, wings, names = await _load_maps(db, unique)
    return {
        "visitors": [
            _serialize(
                visit,
                visitors.get(visit.visitor_id),
                flats.get(visit.flat_id),
                wings.get(visit.wing_id),
                names.get(visit.occupancy_id),
            )
            for visit in unique
        ]
    }


async def upload_photo(
    db: AsyncSession,
    *,
    actor_society_id: UUID | None,
    photo_bytes: bytes,
    photo_filename: str | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    url = save_visitor_photo(
        society_id=society_id, data=photo_bytes, filename=photo_filename
    )
    return {"photoUrl": url, "photo_url": url}


async def search_flats(
    db: AsyncSession, *, actor_society_id: UUID | None, q: str | None, limit: int = 20
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    stmt = (
        select(Flat, Wing)
        .join(Wing, Wing.id == Flat.wing_id)
        .where(Flat.society_id == society_id, Flat.is_active.is_(True))
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Flat.flat_no.ilike(term),
                Wing.code.ilike(term),
                func.concat(Wing.code, "-", Flat.flat_no).ilike(term),
            )
        )
    rows = (await db.execute(stmt.order_by(Wing.code.asc(), Flat.flat_no.asc()).limit(limit))).all()
    flat_ids = [flat.id for flat, _ in rows]
    occs: dict[UUID, Occupancy] = {}
    if flat_ids:
        occ_rows = (
            await db.execute(
                select(Occupancy).where(
                    Occupancy.society_id == society_id,
                    Occupancy.flat_id.in_(flat_ids),
                    Occupancy.status == "active",
                    Occupancy.is_active.is_(True),
                )
            )
        ).scalars().all()
        for occ in occ_rows:
            current = occs.get(occ.flat_id)
            if current is None or (occ.is_primary and not current.is_primary):
                occs[occ.flat_id] = occ
    resident_ids = {o.resident_id for o in occs.values()}
    residents: dict[UUID, Resident] = {}
    if resident_ids:
        residents = {
            row.id: row
            for row in (
                await db.execute(select(Resident).where(Resident.id.in_(resident_ids)))
            ).scalars().all()
        }

    items = []
    for flat, wing in rows:
        occ = occs.get(flat.id)
        resident = residents.get(occ.resident_id) if occ else None
        items.append(
            {
                "id": str(flat.id),
                "flatId": str(flat.id),
                "flat_number": _flat_label(flat, wing),
                "flatNo": flat.flat_no,
                "wingCode": wing.code,
                "occupancyId": str(occ.id) if occ else None,
                "resident_name": resident.name if resident else None,
                "residentName": resident.name if resident else None,
                "phone": resident.phone if resident else None,
            }
        )
    return {"flats": items}


async def flat_contact(
    db: AsyncSession, flat_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    flat = (
        await db.execute(
            select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id)
        )
    ).scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")
    occ = (
        await db.execute(
            select(Occupancy)
            .where(
                Occupancy.society_id == society_id,
                Occupancy.flat_id == flat_id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
            .order_by(Occupancy.is_primary.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not occ:
        raise ApiError(404, "No active resident for this flat")
    resident = (
        await db.execute(select(Resident).where(Resident.id == occ.resident_id))
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")
    return {"phone": resident.phone, "name": resident.name, "residentId": str(resident.id)}


async def log_call(
    db: AsyncSession,
    body: GuardCallLogCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visit = await _get_visit(db, body.visitorId, society_id)
    meta = dict(visit.metadata_json or {})
    logs = list(meta.get("callLogs") or [])
    entry = {
        "guardId": str(actor_id),
        "timestamp": utcnow().isoformat(),
        "notes": body.notes,
    }
    logs.append(entry)
    meta["callLogs"] = logs
    visit.metadata_json = meta
    apply_update_audit(visit, actor_id)
    await db.commit()
    return {"callLog": entry, "visitor": await _serialize_one(db, visit)}
