import math
import mimetypes
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session, selectinload

from modules.guard_common.deps import GuardUser
from modules.guard_common.settings import MOVE_OUT_UPLOAD_DIR
from modules.move_out.models import (
    STATUSES,
    STATUS_ALLOWED,
    STATUS_PENDING,
    STATUS_READY,
    MoveOut,
    MoveOutFile,
    now_ist,
)
from modules.move_out.schemas import (
    MoveOutCounts,
    MoveOutFileItem,
    MoveOutItem,
    MoveOutListData,
    Pagination,
)

MOVE_OUT_SORTS = {
    "residentName": MoveOut.resident_name,
    "flatNo": MoveOut.flat_no,
    "buildingNo": MoveOut.building_no,
    "wingNo": MoveOut.wing_no,
    "moveOutDate": MoveOut.move_out_date,
    "allowedAt": MoveOut.allowed_at,
}

_ALL_YES = and_(
    MoveOut.leave_license.is_(True),
    MoveOut.tenant_id_proof.is_(True),
    MoveOut.owner_confirmation.is_(True),
    MoveOut.dues_clearance.is_(True),
)
_NOT_ALL_YES = or_(
    MoveOut.leave_license.is_(False),
    MoveOut.tenant_id_proof.is_(False),
    MoveOut.owner_confirmation.is_(False),
    MoveOut.dues_clearance.is_(False),
)


def _pagination(page: int, page_size: int, total: int) -> Pagination:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return Pagination(
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


def _direction(column, sort_order: str):
    if sort_order == "asc":
        return column.asc().nulls_last()
    return column.desc().nulls_last()


def _checks_complete(row: MoveOut) -> bool:
    return bool(
        row.leave_license and row.tenant_id_proof and row.owner_confirmation and row.dues_clearance
    )


def _status(row: MoveOut) -> str:
    if row.allowed_at is not None:
        return STATUS_ALLOWED
    if _checks_complete(row):
        return STATUS_READY
    return STATUS_PENDING


def _file_item(move_out_id: int, file: MoveOutFile) -> MoveOutFileItem:
    return MoveOutFileItem(
        id=file.id,
        title=file.title,
        fileName=file.file_name,
        sizeBytes=file.size_bytes,
        viewUrl=f"/guard/move-out/{move_out_id}/files/{file.id}",
    )


def _to_item(row: MoveOut) -> MoveOutItem:
    status_name = _status(row)
    return MoveOutItem(
        id=row.id,
        residentName=row.resident_name,
        flatNo=row.flat_no,
        buildingNo=row.building_no,
        wingNo=row.wing_no,
        moveOutDate=row.move_out_date,
        leaveLicense=row.leave_license,
        tenantIdProof=row.tenant_id_proof,
        ownerConfirmation=row.owner_confirmation,
        duesClearance=row.dues_clearance,
        status=status_name,
        canAllow=status_name == STATUS_READY,
        allowedAt=row.allowed_at,
        documents=[_file_item(row.id, file) for file in row.files],
    )


def _base(db: Session, society_id: int):
    return (
        db.query(MoveOut)
        .options(selectinload(MoveOut.files))
        .filter(MoveOut.society_id == society_id)
    )


def _counts(db: Session, society_id: int) -> MoveOutCounts:
    base = db.query(MoveOut).filter(MoveOut.society_id == society_id)
    return MoveOutCounts(
        all=base.count(),
        pending=base.filter(MoveOut.allowed_at.is_(None), _NOT_ALL_YES).count(),
        ready=base.filter(MoveOut.allowed_at.is_(None), _ALL_YES).count(),
        allowed=base.filter(MoveOut.allowed_at.isnot(None)).count(),
    )


def _apply_status(query, status_name: str):
    if status_name == STATUS_ALLOWED:
        return query.filter(MoveOut.allowed_at.isnot(None))
    if status_name == STATUS_READY:
        return query.filter(MoveOut.allowed_at.is_(None), _ALL_YES)
    if status_name == STATUS_PENDING:
        return query.filter(MoveOut.allowed_at.is_(None), _NOT_ALL_YES)
    return query


def _move_out(db: Session, society_id: int, move_out_id: int) -> MoveOut:
    row = _base(db, society_id).filter(MoveOut.id == move_out_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Move-out not found")
    return row


def _safe_file(stored: str) -> Path:
    root = Path(MOVE_OUT_UPLOAD_DIR).resolve()
    candidate = Path(stored)
    if not candidate.is_absolute():
        from_cwd = (Path.cwd() / candidate).resolve()
        try:
            from_cwd.relative_to(root)
            candidate = from_cwd
        except ValueError:
            candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Move-out file not found") from None
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Move-out file not found")
    return candidate


def list_move_outs(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> MoveOutListData:
    page_size = min(page_size, 100)
    clean_status = (status_filter or "all").strip().lower()
    if clean_status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    order = (sort_order or "desc").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc"

    society_id = current_user.society_id
    query = _apply_status(_base(db, society_id), clean_status)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (MoveOut.resident_name.ilike(term)) | (MoveOut.flat_no.ilike(term))
        )

    if sort_by == "status":
        rank = case(
            (MoveOut.allowed_at.isnot(None), 2),
            (_ALL_YES, 1),
            else_=0,
        )
        primary = rank.asc() if order == "asc" else rank.desc()
        query = query.order_by(primary, MoveOut.move_out_date.desc(), MoveOut.id.desc())
    else:
        column = MOVE_OUT_SORTS.get(sort_by, MoveOut.move_out_date)
        query = query.order_by(_direction(column, order), MoveOut.id.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return MoveOutListData(
        counts=_counts(db, society_id),
        items=[_to_item(row) for row in rows],
        pagination=_pagination(page, page_size, total),
    )


def get_move_out(db: Session, current_user: GuardUser, move_out_id: int) -> MoveOutItem:
    return _to_item(_move_out(db, current_user.society_id, move_out_id))


def allow_move_out(db: Session, current_user: GuardUser, move_out_id: int) -> MoveOutItem:
    row = _move_out(db, current_user.society_id, move_out_id)
    if row.allowed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Move-out is already allowed",
        )
    if not _checks_complete(row):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Allow to go is available only when every check is Yes",
        )

    row.allowed_at = now_ist()
    row.allowed_by = current_user.id
    db.commit()
    return _to_item(_move_out(db, current_user.society_id, move_out_id))


def open_move_out_file(
    db: Session,
    current_user: GuardUser,
    move_out_id: int,
    file_id: int,
) -> FileResponse:
    row = _move_out(db, current_user.society_id, move_out_id)
    file_row = next((item for item in row.files if item.id == file_id), None)
    if file_row is None or file_row.society_id != current_user.society_id:
        raise HTTPException(status_code=404, detail="Move-out file not found")

    path = _safe_file(file_row.file_path)
    media_type = mimetypes.guess_type(file_row.file_name or path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=file_row.file_name or path.name,
        content_disposition_type="inline",
    )
