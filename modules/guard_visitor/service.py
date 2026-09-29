import math
import os
import re
import shutil
import uuid
from datetime import date, datetime, time
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Query, Session, contains_eager

from modules.guard_common.deps import GuardUser
from modules.guard_common.residents import find_active_occupancy
from modules.guard_common.settings import MAX_VISITOR_PHOTO_BYTES, VISITOR_UPLOAD_DIR
from modules.guard_visitor.models import (
    IST,
    UI_APPROVED,
    UI_CANCELLED,
    UI_EXITED,
    UI_INSIDE,
    UI_PENDING,
    UI_REJECTED,
    VISIT_CANCELLED,
    VISIT_CHECKED_IN,
    VISIT_CHECKED_OUT,
    VISIT_REJECTED,
    VISIT_SCHEDULED,
    VISIT_WAITING,
    VisitGateEntry,
    now_ist,
)
from modules.guard_visitor.schemas import (
    Pagination,
    VisitorItem,
    VisitorListData,
    VisitorRecentData,
)
from modules.notification import service as notification_service
from modules.resident.models import Building, Flat, Occupancy
from modules.visitor import crud as visitor_crud
from modules.visitor.models import Visit, Visitor

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PURPOSES = {
    "guest",
    "delivery",
    "courier",
    "cab",
    "maid",
    "driver",
    "technician",
    "vendor",
    "other",
}
ALLOWED_VEHICLE_TYPES = {
    "car",
    "bike",
    "scooter",
    "ev",
    "commercial",
    "bicycle",
    "other",
}
CHECK_IN_READY = (VISIT_SCHEDULED, VISIT_WAITING)


def status_clause(ui_status: str):
    """Translate a Guard Panel status into a filter on the shared `visits` table."""
    if ui_status == UI_PENDING:
        return and_(Visit.status == VISIT_WAITING, Visit.is_preapproved.is_(False))
    if ui_status == UI_APPROVED:
        return and_(Visit.status.in_(CHECK_IN_READY), Visit.is_preapproved.is_(True))
    if ui_status == UI_INSIDE:
        return Visit.status == VISIT_CHECKED_IN
    if ui_status == UI_EXITED:
        return Visit.status == VISIT_CHECKED_OUT
    if ui_status == UI_REJECTED:
        return Visit.status == VISIT_REJECTED
    if ui_status == UI_CANCELLED:
        return Visit.status == VISIT_CANCELLED
    raise HTTPException(status_code=400, detail="Invalid status filter")


def _ui_status(visit: Visit) -> str:
    if visit.status == VISIT_CHECKED_IN:
        return UI_INSIDE
    if visit.status == VISIT_CHECKED_OUT:
        return UI_EXITED
    if visit.status in CHECK_IN_READY:
        return UI_APPROVED if visit.is_preapproved else UI_PENDING
    return visit.status


def _digits_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _photo_url(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def _to_item(
    visit: Visit,
    entry: VisitGateEntry | None,
    flat: Flat,
    building: Building,
) -> VisitorItem:
    return VisitorItem(
        id=visit.id,
        societyId=visit.society_id,
        name=visit.visitor.name,
        phone=visit.visitor.phone,
        purpose=visit.purpose or visit.visitor_type,
        buildingNo=building.name,
        wingNo=entry.wing_no if entry else None,
        flatNo=flat.number,
        personCount=entry.person_count if entry else 1,
        vehicleNumber=entry.vehicle_number if entry else None,
        vehicleType=entry.vehicle_type if entry else None,
        notifyResident=bool(entry.notify_resident) if entry else False,
        preApproved=bool(visit.is_preapproved),
        remarks=(entry.remarks if entry else None) or visit.notes,
        photoUrl=_photo_url(entry.photo_path) if entry else None,
        status=_ui_status(visit),
        recordedBy=entry.recorded_by if entry else None,
        checkInTime=entry.check_in_time if entry else None,
        checkOutTime=entry.check_out_time if entry else None,
        createdAt=visit.created_at,
    )


def base_query(db: Session, society_id: int) -> Query:
    return (
        db.query(Visit, VisitGateEntry, Flat, Building)
        .join(Visitor, Visitor.id == Visit.visitor_id)
        .join(Occupancy, Occupancy.id == Visit.occupancy_id)
        .join(Flat, Flat.id == Occupancy.flat_id)
        .join(Building, Building.id == Flat.building_id)
        .outerjoin(VisitGateEntry, VisitGateEntry.visit_id == Visit.id)
        .options(contains_eager(Visit.visitor))
        .filter(Visit.society_id == society_id)
    )


def _get_row(db: Session, current_user: GuardUser, visit_id: int):
    row = base_query(db, current_user.society_id).filter(Visit.id == visit_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return row


def _upload_dir() -> Path:
    path = Path(VISITOR_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stored_photo_path(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def save_visitor_photo(file: UploadFile | None) -> str | None:
    if file is None or not file.filename:
        return None

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, JPEG, PNG and WEBP images are allowed",
        )

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if file_size > MAX_VISITOR_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5 MB",
        )

    unique_name = f"{uuid.uuid4()}{extension}"
    absolute_path = _upload_dir() / unique_name
    try:
        with open(absolute_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file",
        ) from exc

    return _stored_photo_path(unique_name)


def _remove_file(stored_path: str | None) -> None:
    if not stored_path:
        return
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def create_visitor(
    db: Session,
    current_user: GuardUser,
    *,
    name: str,
    phone: str,
    purpose: str,
    building: str,
    wing: str | None,
    flat: str,
    person_count: int,
    vehicle_number: str | None,
    vehicle_type: str | None,
    notify_resident: str | None,
    pre_approved: str | None,
    remarks: str | None,
    photo: UploadFile | None,
) -> VisitorItem:
    clean_name = (name or "").strip()
    clean_phone = _digits_phone(phone)
    clean_building = (building or "").strip()
    clean_wing = (wing or "").strip() or None
    clean_flat = (flat or "").strip()
    clean_purpose = (purpose or "").strip().lower()

    if not clean_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if len(clean_phone) < 10:
        raise HTTPException(status_code=400, detail="Valid phone is required")
    if not clean_building:
        raise HTTPException(status_code=400, detail="Building number or name is required")
    if clean_wing and len(clean_wing) > 30:
        raise HTTPException(status_code=400, detail="Wing number is too long")
    if not clean_flat:
        raise HTTPException(status_code=400, detail="Visiting flat is required")
    if clean_purpose not in ALLOWED_PURPOSES:
        raise HTTPException(status_code=400, detail="Invalid purpose")
    if person_count < 1:
        raise HTTPException(status_code=400, detail="Number of persons must be at least 1")

    clean_vehicle_type = (vehicle_type or "").strip().lower() or None
    if clean_vehicle_type and clean_vehicle_type not in ALLOWED_VEHICLE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid vehicle type")

    occupancy = find_active_occupancy(db, current_user.society_id, clean_building, clean_flat)
    is_pre_approved = _as_bool(pre_approved, default=False)
    should_notify = _as_bool(notify_resident, default=True)
    clean_remarks = (remarks or "").strip() or None
    now = now_ist()
    photo_path = save_visitor_photo(photo)

    try:
        visitor = visitor_crud.get_or_create_visitor(
            db, current_user.society_id, clean_name, clean_phone
        )
        visit = Visit(
            society_id=current_user.society_id,
            occupancy_id=occupancy.id,
            visitor_id=visitor.id,
            status=VISIT_CHECKED_IN if is_pre_approved else VISIT_WAITING,
            visitor_type=clean_purpose,
            purpose=clean_purpose,
            notes=clean_remarks[:255] if clean_remarks else None,
            is_preapproved=is_pre_approved,
            created_at=now,
        )
        db.add(visit)
        db.flush()
        entry = VisitGateEntry(
            visit_id=visit.id,
            society_id=current_user.society_id,
            wing_no=clean_wing,
            person_count=person_count,
            vehicle_number=(vehicle_number or "").strip().upper() or None,
            vehicle_type=clean_vehicle_type,
            notify_resident=should_notify,
            remarks=clean_remarks,
            photo_path=photo_path,
            recorded_by=current_user.id,
            check_in_time=now if is_pre_approved else None,
            created_at=now,
        )
        db.add(entry)
        if should_notify and not is_pre_approved:
            notification_service.record(
                db,
                user_id=occupancy.resident.user_id,
                society_id=current_user.society_id,
                occupancy_id=occupancy.id,
                category="visitor",
                title="Visitor at gate",
                body=f"{clean_name} is waiting at the gate. Please approve or reject.",
            )
        db.commit()
    except Exception:
        db.rollback()
        _remove_file(photo_path)
        raise

    return _to_item(visit, entry, occupancy.flat, occupancy.flat.building)


def list_visitors(
    db: Session,
    current_user: GuardUser,
    *,
    status_filter: str | None,
    search: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> VisitorListData:
    page_size = min(page_size, 100)
    query = base_query(db, current_user.society_id)

    if status_filter:
        query = query.filter(status_clause(status_filter.strip().lower()))

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )

    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        query = query.filter(Visit.created_at >= start)

    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        query = query.filter(Visit.created_at <= end)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Visitor.name.ilike(term))
            | (Visitor.phone.ilike(term))
            | (Building.name.ilike(term))
            | (Flat.number.ilike(term))
            | (VisitGateEntry.wing_no.ilike(term))
            | (VisitGateEntry.vehicle_number.ilike(term))
        )

    sort_map = {
        "createdAt": Visit.created_at,
        "name": Visitor.name,
        "checkInTime": VisitGateEntry.check_in_time,
    }
    column = sort_map.get(sort_by, Visit.created_at)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc()
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size)) if total else 1

    return VisitorListData(
        items=[_to_item(*row) for row in rows],
        pagination=Pagination(
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            hasNext=page < total_pages,
            hasPrev=page > 1,
        ),
    )


def recent_visitors(
    db: Session,
    current_user: GuardUser,
    *,
    limit: int,
) -> VisitorRecentData:
    limit = min(max(limit, 1), 50)
    latest_ids = (
        db.query(func.max(Visit.id))
        .join(VisitGateEntry, VisitGateEntry.visit_id == Visit.id)
        .filter(
            Visit.society_id == current_user.society_id,
            VisitGateEntry.recorded_by == current_user.id,
        )
        .group_by(Visit.visitor_id)
    )
    rows = (
        base_query(db, current_user.society_id)
        .filter(Visit.id.in_(latest_ids))
        .order_by(Visit.created_at.desc())
        .limit(limit)
        .all()
    )
    return VisitorRecentData(items=[_to_item(*row) for row in rows])


def get_visitor(
    db: Session,
    current_user: GuardUser,
    visit_id: int,
) -> VisitorItem:
    return _to_item(*_get_row(db, current_user, visit_id))


def check_in_visitor(
    db: Session,
    current_user: GuardUser,
    visit_id: int,
) -> VisitorItem:
    """Guard marks entry only after the resident approved or pre-invited the visitor."""
    visit, entry, flat, building = _get_row(db, current_user, visit_id)
    if visit.status not in CHECK_IN_READY or not visit.is_preapproved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Visitor must be approved by resident before check-in",
        )

    now = now_ist()
    visit.status = VISIT_CHECKED_IN
    if entry is None:
        entry = VisitGateEntry(
            visit_id=visit.id,
            society_id=visit.society_id,
            recorded_by=current_user.id,
            created_at=now,
        )
        db.add(entry)
    entry.check_in_time = now
    db.commit()
    return _to_item(visit, entry, flat, building)


def exit_visitor(
    db: Session,
    current_user: GuardUser,
    visit_id: int,
) -> VisitorItem:
    visit, entry, flat, building = _get_row(db, current_user, visit_id)
    if visit.status != VISIT_CHECKED_IN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Visitor is not currently inside",
        )

    now = now_ist()
    visit.status = VISIT_CHECKED_OUT
    if entry is None:
        entry = VisitGateEntry(
            visit_id=visit.id,
            society_id=visit.society_id,
            recorded_by=current_user.id,
            created_at=now,
        )
        db.add(entry)
    entry.check_out_time = now
    db.commit()
    return _to_item(visit, entry, flat, building)
