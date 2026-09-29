import math
import os
import re
import shutil
import uuid
from datetime import date, datetime, time
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from modules.guard_common.deps import GuardUser
from modules.guard_common.settings import CAB_UPLOAD_DIR, MAX_CAB_PHOTO_BYTES
from modules.cab.models import (
    IST,
    STATUS_APPROVED,
    STATUS_EXITED,
    STATUS_INSIDE,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUSES,
    Cab,
    now_ist,
)
from modules.cab.schemas import CabItem, CabListData, Pagination

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _blank_to_none(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _vehicle_number(value: str) -> str:
    return re.sub(r"\s+", "", (value or "")).upper()


def _photo_url(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def _to_item(cab: Cab) -> CabItem:
    return CabItem(
        id=cab.id,
        societyId=cab.society_id,
        vehicleNumber=cab.vehicle_number,
        driverName=cab.driver_name,
        cabService=cab.cab_service,
        buildingNo=cab.building_no,
        wingNo=cab.wing_no,
        flatNo=cab.flat_no,
        purpose=cab.purpose,
        photoUrl=_photo_url(cab.photo_path),
        status=cab.status,
        recordedBy=cab.recorded_by,
        entryTime=cab.entry_time,
        exitTime=cab.exit_time,
        createdAt=cab.created_at,
    )


def _upload_dir() -> Path:
    path = Path(CAB_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stored_photo_path(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def save_cab_photo(file: UploadFile | None) -> str | None:
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
    if file_size > MAX_CAB_PHOTO_BYTES:
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


def _get_for_society(
    db: Session,
    current_user: GuardUser,
    cab_id: int,
) -> Cab:
    cab = (
        db.query(Cab)
        .filter(
            Cab.id == cab_id,
            Cab.society_id == current_user.society_id,
        )
        .first()
    )
    if not cab:
        raise HTTPException(status_code=404, detail="Cab not found")
    return cab


def create_cab(
    db: Session,
    current_user: GuardUser,
    *,
    vehicle_number: str,
    cab_service: str,
    building: str,
    wing: str,
    flat: str,
    purpose: str,
    driver_name: str | None,
    photo: UploadFile | None,
) -> CabItem:
    clean_vehicle = _vehicle_number(vehicle_number)
    clean_service = (cab_service or "").strip()
    clean_building = (building or "").strip()
    clean_wing = (wing or "").strip()
    clean_flat = (flat or "").strip()
    clean_purpose = (purpose or "").strip()

    if not clean_vehicle:
        raise HTTPException(status_code=400, detail="Vehicle number is required")
    if len(clean_vehicle) > 20:
        raise HTTPException(status_code=400, detail="Vehicle number is too long")
    if not clean_service:
        raise HTTPException(status_code=400, detail="Cab service is required")
    if len(clean_service) > 50:
        raise HTTPException(status_code=400, detail="Cab service name is too long")
    if not clean_building:
        raise HTTPException(status_code=400, detail="Building number or name is required")
    if len(clean_building) > 80:
        raise HTTPException(status_code=400, detail="Building number or name is too long")
    if not clean_wing:
        raise HTTPException(status_code=400, detail="Wing number is required")
    if len(clean_wing) > 30:
        raise HTTPException(status_code=400, detail="Wing number is too long")
    if not clean_flat:
        raise HTTPException(status_code=400, detail="Resident / flat is required")
    if not clean_purpose:
        raise HTTPException(status_code=400, detail="Purpose is required")
    if len(clean_purpose) > 50:
        raise HTTPException(status_code=400, detail="Purpose is too long")

    clean_driver = _blank_to_none(driver_name)
    if clean_driver and len(clean_driver) > 150:
        raise HTTPException(status_code=400, detail="Driver name is too long")

    now = now_ist()
    photo_path = save_cab_photo(photo)
    cab = Cab(
        society_id=current_user.society_id,
        vehicle_number=clean_vehicle,
        driver_name=clean_driver,
        cab_service=clean_service,
        building_no=clean_building,
        wing_no=clean_wing,
        flat_no=clean_flat,
        purpose=clean_purpose,
        photo_path=photo_path,
        status=STATUS_PENDING,
        recorded_by=current_user.id,
        entry_time=None,
        exit_time=None,
        created_at=now,
    )
    db.add(cab)
    try:
        db.commit()
        db.refresh(cab)
    except Exception:
        db.rollback()
        _remove_file(photo_path)
        raise

    return _to_item(cab)


def list_cabs(
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
) -> CabListData:
    page_size = min(page_size, 100)
    query = db.query(Cab).filter(Cab.society_id == current_user.society_id)

    if status_filter:
        clean_status = status_filter.strip().lower()
        if clean_status not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Cab.status == clean_status)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )

    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        query = query.filter(Cab.created_at >= start)

    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        query = query.filter(Cab.created_at <= end)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Cab.vehicle_number.ilike(term))
            | (Cab.driver_name.ilike(term))
            | (Cab.building_no.ilike(term))
            | (Cab.wing_no.ilike(term))
            | (Cab.flat_no.ilike(term))
            | (Cab.cab_service.ilike(term))
            | (Cab.purpose.ilike(term))
        )

    sort_map = {
        "createdAt": Cab.created_at,
        "driverName": Cab.driver_name,
        "vehicleNumber": Cab.vehicle_number,
        "entryTime": Cab.entry_time,
    }
    column = sort_map.get(sort_by, Cab.created_at)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc()
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size)) if total else 1

    return CabListData(
        items=[_to_item(row) for row in rows],
        pagination=Pagination(
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
            hasNext=page < total_pages,
            hasPrev=page > 1,
        ),
    )


def get_cab(
    db: Session,
    current_user: GuardUser,
    cab_id: int,
) -> CabItem:
    return _to_item(_get_for_society(db, current_user, cab_id))


def check_in_cab(
    db: Session,
    current_user: GuardUser,
    cab_id: int,
) -> CabItem:
    """Guard lets the cab in only after the resident has approved."""
    cab = _get_for_society(db, current_user, cab_id)
    if cab.status == STATUS_REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cab was rejected by resident",
        )
    if cab.status != STATUS_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cab must be approved by resident before check-in",
        )

    cab.status = STATUS_INSIDE
    cab.entry_time = now_ist()
    db.commit()
    db.refresh(cab)
    return _to_item(cab)


def exit_cab(
    db: Session,
    current_user: GuardUser,
    cab_id: int,
) -> CabItem:
    cab = _get_for_society(db, current_user, cab_id)
    if cab.status != STATUS_INSIDE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cab is not currently inside",
        )

    cab.status = STATUS_EXITED
    cab.exit_time = now_ist()
    db.commit()
    db.refresh(cab)
    return _to_item(cab)
