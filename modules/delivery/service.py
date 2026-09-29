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
from modules.guard_common.settings import DELIVERY_UPLOAD_DIR, MAX_DELIVERY_PHOTO_BYTES
from modules.delivery.models import (
    IST,
    STATUS_APPROVED,
    STATUS_EXITED,
    STATUS_INSIDE,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUSES,
    Delivery,
    now_ist,
)
from modules.delivery.schemas import DeliveryItem, DeliveryListData, Pagination

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _digits_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def _blank_to_none(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _photo_url(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def _to_item(delivery: Delivery) -> DeliveryItem:
    return DeliveryItem(
        id=delivery.id,
        societyId=delivery.society_id,
        courierName=delivery.courier_name,
        phone=delivery.phone,
        company=delivery.company,
        trackingId=delivery.tracking_id,
        buildingNo=delivery.building_no,
        wingNo=delivery.wing_no,
        flatNo=delivery.flat_no,
        parcelNote=delivery.parcel_note,
        photoUrl=_photo_url(delivery.photo_path),
        status=delivery.status,
        receivedBy=delivery.received_by,
        recordedBy=delivery.recorded_by,
        entryTime=delivery.entry_time,
        exitTime=delivery.exit_time,
        createdAt=delivery.created_at,
    )


def _upload_dir() -> Path:
    path = Path(DELIVERY_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stored_photo_path(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def save_delivery_photo(file: UploadFile | None) -> str | None:
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
    if file_size > MAX_DELIVERY_PHOTO_BYTES:
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
    delivery_id: int,
) -> Delivery:
    delivery = (
        db.query(Delivery)
        .filter(
            Delivery.id == delivery_id,
            Delivery.society_id == current_user.society_id,
        )
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


def create_delivery(
    db: Session,
    current_user: GuardUser,
    *,
    courier_name: str,
    phone: str,
    company: str,
    building: str,
    wing: str,
    flat: str,
    tracking_id: str | None,
    parcel_note: str | None,
    photo: UploadFile | None,
) -> DeliveryItem:
    clean_name = (courier_name or "").strip()
    clean_phone = _digits_phone(phone)
    clean_company = (company or "").strip().lower()
    clean_building = (building or "").strip()
    clean_wing = (wing or "").strip()
    clean_flat = (flat or "").strip()

    if not clean_name:
        raise HTTPException(status_code=400, detail="Courier name is required")
    if len(clean_phone) != 10:
        raise HTTPException(status_code=400, detail="Valid 10-digit phone is required")
    if not clean_company:
        raise HTTPException(status_code=400, detail="Company is required")
    if len(clean_company) > 50:
        raise HTTPException(status_code=400, detail="Company name is too long")
    if not clean_building:
        raise HTTPException(status_code=400, detail="Building number or name is required")
    if len(clean_building) > 80:
        raise HTTPException(status_code=400, detail="Building number or name is too long")
    if not clean_wing:
        raise HTTPException(status_code=400, detail="Wing number is required")
    if len(clean_wing) > 30:
        raise HTTPException(status_code=400, detail="Wing number is too long")
    if not clean_flat:
        raise HTTPException(status_code=400, detail="Deliver to flat is required")

    now = now_ist()
    photo_path = save_delivery_photo(photo)
    delivery = Delivery(
        society_id=current_user.society_id,
        courier_name=clean_name,
        phone=clean_phone,
        company=clean_company,
        tracking_id=_blank_to_none(tracking_id),
        building_no=clean_building,
        wing_no=clean_wing,
        flat_no=clean_flat,
        parcel_note=_blank_to_none(parcel_note),
        photo_path=photo_path,
        status=STATUS_PENDING,
        received_by=None,
        recorded_by=current_user.id,
        entry_time=None,
        exit_time=None,
        created_at=now,
    )
    db.add(delivery)
    try:
        db.commit()
        db.refresh(delivery)
    except Exception:
        db.rollback()
        _remove_file(photo_path)
        raise

    return _to_item(delivery)


def list_deliveries(
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
) -> DeliveryListData:
    page_size = min(page_size, 100)
    query = db.query(Delivery).filter(Delivery.society_id == current_user.society_id)

    if status_filter:
        clean_status = status_filter.strip().lower()
        if clean_status not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Delivery.status == clean_status)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be on or before 'to' date",
        )

    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=IST)
        query = query.filter(Delivery.created_at >= start)

    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=IST)
        query = query.filter(Delivery.created_at <= end)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Delivery.courier_name.ilike(term))
            | (Delivery.phone.ilike(term))
            | (Delivery.building_no.ilike(term))
            | (Delivery.wing_no.ilike(term))
            | (Delivery.flat_no.ilike(term))
            | (Delivery.company.ilike(term))
            | (Delivery.tracking_id.ilike(term))
        )

    sort_map = {
        "createdAt": Delivery.created_at,
        "courierName": Delivery.courier_name,
        "entryTime": Delivery.entry_time,
    }
    column = sort_map.get(sort_by, Delivery.created_at)
    query = query.order_by(
        column.asc() if (sort_order or "desc").lower() == "asc" else column.desc()
    )

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, math.ceil(total / page_size)) if total else 1

    return DeliveryListData(
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


def get_delivery(
    db: Session,
    current_user: GuardUser,
    delivery_id: int,
) -> DeliveryItem:
    return _to_item(_get_for_society(db, current_user, delivery_id))


def check_in_delivery(
    db: Session,
    current_user: GuardUser,
    delivery_id: int,
) -> DeliveryItem:
    """Guard lets the courier in only after the resident has approved."""
    delivery = _get_for_society(db, current_user, delivery_id)
    if delivery.status == STATUS_REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery was rejected by resident",
        )
    if delivery.status != STATUS_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery must be approved by resident before check-in",
        )

    delivery.status = STATUS_INSIDE
    delivery.entry_time = now_ist()
    db.commit()
    db.refresh(delivery)
    return _to_item(delivery)


def exit_delivery(
    db: Session,
    current_user: GuardUser,
    delivery_id: int,
) -> DeliveryItem:
    delivery = _get_for_society(db, current_user, delivery_id)
    if delivery.status != STATUS_INSIDE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Delivery is not currently inside",
        )

    delivery.status = STATUS_EXITED
    delivery.exit_time = now_ist()
    db.commit()
    db.refresh(delivery)
    return _to_item(delivery)
