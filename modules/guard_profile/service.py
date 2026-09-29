import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from auth.models import User
from core.security import hash_password, verify_password
from modules.guard_common.deps import GuardUser
from modules.guard_common.settings import GUARD_PHOTO_UPLOAD_DIR, MAX_GUARD_PHOTO_BYTES
from modules.guard_profile.models import GuardProfile, now_ist
from modules.guard_profile.schemas import ChangePasswordIn, GuardProfileItem, GuardProfileUpdate

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _photo_url(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    return "/" + stored_path.replace("\\", "/").lstrip("/")


def _to_item(row: GuardProfile) -> GuardProfileItem:
    return GuardProfileItem(
        id=row.id,
        userId=row.user_id,
        name=row.name,
        email=row.email,
        phone=row.phone,
        designation=row.designation,
        staffCode=row.staff_code,
        gateName=row.gate_name,
        gateCode=row.gate_code,
        photoUrl=_photo_url(row.photo_path),
        joiningDate=row.joining_date,
        isActive=bool(row.is_active),
    )


def _own_profile(db: Session, current_user: GuardUser) -> GuardProfile:
    row = (
        db.query(GuardProfile)
        .filter(
            GuardProfile.user_id == current_user.id,
            GuardProfile.society_id == current_user.society_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Guard profile not found")
    return row


def _upload_dir() -> Path:
    path = Path(GUARD_PHOTO_UPLOAD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stored_photo_path(filename: str) -> str:
    absolute = (_upload_dir() / filename).resolve()
    try:
        return absolute.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absolute.as_posix()


def _remove_file(stored_path: str | None) -> None:
    if not stored_path:
        return
    root = Path(GUARD_PHOTO_UPLOAD_DIR).resolve()
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def _save_photo(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo file is required",
        )

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
    if file_size > MAX_GUARD_PHOTO_BYTES:
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


def get_profile(db: Session, current_user: GuardUser) -> GuardProfileItem:
    return _to_item(_own_profile(db, current_user))


def update_profile(
    db: Session, current_user: GuardUser, data: GuardProfileUpdate
) -> GuardProfileItem:
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")
    if len(name) > 150:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is too long")

    phone = (data.phone or "").strip() or None
    if phone is not None and (len(phone) < 10 or len(phone) > 20):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone must be between 10 and 20 characters",
        )

    row = _own_profile(db, current_user)
    row.name = name
    row.phone = phone
    row.updated_at = now_ist()
    db.commit()
    db.refresh(row)
    return _to_item(row)


def change_password(db: Session, current_user: GuardUser, data: ChangePasswordIn) -> None:
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(data.current_password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is wrong")
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )
    user.password = hash_password(data.new_password)
    db.commit()


def replace_photo(db: Session, current_user: GuardUser, photo: UploadFile) -> GuardProfileItem:
    row = _own_profile(db, current_user)
    new_path = _save_photo(photo)
    old_path = row.photo_path
    row.photo_path = new_path
    row.updated_at = now_ist()
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        _remove_file(new_path)
        raise
    if old_path and old_path != new_path:
        _remove_file(old_path)
    return _to_item(row)


def clear_photo(db: Session, current_user: GuardUser) -> GuardProfileItem:
    row = _own_profile(db, current_user)
    old_path = row.photo_path
    row.photo_path = None
    row.updated_at = now_ist()
    db.commit()
    db.refresh(row)
    _remove_file(old_path)
    return _to_item(row)
