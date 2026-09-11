"""Local disk uploads — original file on disk, public path stored in DB."""

from __future__ import annotations

import base64
import re
import time
import uuid
from pathlib import Path

from Core.config import BASE_DIR
from Utils.errors import ApiError

UPLOADS_DIR = BASE_DIR / "uploads"
PUBLIC_PREFIX = "/uploads"

# SaffoCare-style purpose folders: uploads/{role}_image/{filename}
UPLOAD_FOLDERS = (
    "visitor_image",
    "guard_image",
    "resident_image",
    "staff_image",
    "admin_image",
)
VISITOR_UPLOADS_DIR = UPLOADS_DIR / "visitor_image"

MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

_DATA_URL_RE = re.compile(
    r"^data:(image/(jpeg|jpg|png|webp));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)

def ensure_upload_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for name in UPLOAD_FOLDERS:
        (UPLOADS_DIR / name).mkdir(parents=True, exist_ok=True)


def _ext_from_bytes(data: bytes, fallback: str = ".jpg") -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    ext = fallback.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in ALLOWED_EXTS:
        raise ApiError(422, "Photo must be JPG, PNG, or WEBP")
    return ext


def _decode_photo_payload(value: str) -> tuple[bytes, str]:
    raw = value.strip()
    match = _DATA_URL_RE.match(raw)
    if match:
        mime = match.group(1).lower()
        payload = match.group(3)
        ext = ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
        try:
            data = base64.b64decode(payload, validate=False)
        except Exception as exc:
            raise ApiError(422, "Invalid photo data") from exc
        return data, ext
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as exc:
        raise ApiError(422, "Invalid photo data") from exc
    if len(data) < 32:
        raise ApiError(422, "Invalid photo data")
    return data, _ext_from_bytes(data)


def save_visitor_photo(
    *,
    society_id: uuid.UUID,
    data: bytes,
    filename: str | None = None,
) -> str:
    if not data:
        raise ApiError(422, "Photo file is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise ApiError(422, "Photo must be 5MB or smaller")

    fallback = Path(filename or "photo.jpg").suffix.lower() or ".jpg"
    ext = _ext_from_bytes(data, fallback)
    ensure_upload_dirs()
    original = Path(filename or "photo").stem
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "", original)[:40] or "photo"
    stored_name = f"{int(time.time() * 1000)}-{safe}{ext}"
    dest = VISITOR_UPLOADS_DIR / stored_name
    dest.write_bytes(data)
    return f"{PUBLIC_PREFIX}/visitor_image/{stored_name}"


def save_visitor_photo_from_payload(society_id: uuid.UUID, value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    if raw.startswith(PUBLIC_PREFIX + "/"):
        return raw
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw[:500]
    data, ext = _decode_photo_payload(raw)
    return save_visitor_photo(society_id=society_id, data=data, filename=f"photo{ext}")
