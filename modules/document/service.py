import math
import mimetypes
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from modules.guard_common.deps import GuardUser
from modules.guard_common.settings import DOCUMENT_UPLOAD_DIR
from modules.document.models import CATEGORIES, CATEGORY_SECURITY, CATEGORY_SOCIETY, GateDocument
from modules.document.schemas import DocumentCounts, DocumentItem, DocumentListData, Pagination

DOCUMENT_SORTS = {
    "title": GateDocument.title,
    "category": GateDocument.category,
    "sizeBytes": GateDocument.size_bytes,
    "publishedAt": GateDocument.published_at,
    "fileName": GateDocument.file_name,
}


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


def _to_item(row: GateDocument) -> DocumentItem:
    return DocumentItem(
        id=row.id,
        title=row.title,
        category=row.category,
        sizeBytes=row.size_bytes,
        publishedAt=row.published_at,
        fileName=row.file_name,
        viewUrl=f"/guard/documents/{row.id}/view",
        downloadUrl=f"/guard/documents/{row.id}/download",
    )


def _counts(db: Session, society_id: int) -> DocumentCounts:
    base = db.query(GateDocument).filter(GateDocument.society_id == society_id)
    return DocumentCounts(
        all=base.count(),
        security=base.filter(GateDocument.category == CATEGORY_SECURITY).count(),
        society=base.filter(GateDocument.category == CATEGORY_SOCIETY).count(),
    )


def _document(db: Session, society_id: int, document_id: int) -> GateDocument:
    row = (
        db.query(GateDocument)
        .filter(GateDocument.id == document_id, GateDocument.society_id == society_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


def _safe_file(stored: str) -> Path:
    root = Path(DOCUMENT_UPLOAD_DIR).resolve()
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
        raise HTTPException(status_code=404, detail="Document file not found") from None
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return candidate


def list_documents(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    category: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> DocumentListData:
    page_size = min(page_size, 100)
    clean_category = (category or "all").strip().lower()
    if clean_category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category filter")

    order = (sort_order or "desc").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc"

    society_id = current_user.society_id
    query = db.query(GateDocument).filter(GateDocument.society_id == society_id)
    if clean_category != "all":
        query = query.filter(GateDocument.category == clean_category)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (GateDocument.title.ilike(term)) | (GateDocument.file_name.ilike(term))
        )

    column = DOCUMENT_SORTS.get(sort_by, GateDocument.published_at)
    query = query.order_by(_direction(column, order), GateDocument.id.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return DocumentListData(
        counts=_counts(db, society_id),
        items=[_to_item(row) for row in rows],
        pagination=_pagination(page, page_size, total),
    )


def get_document(db: Session, current_user: GuardUser, document_id: int) -> DocumentItem:
    return _to_item(_document(db, current_user.society_id, document_id))


def open_document(
    db: Session,
    current_user: GuardUser,
    document_id: int,
    *,
    inline: bool,
) -> FileResponse:
    row = _document(db, current_user.society_id, document_id)
    path = _safe_file(row.file_path)
    media_type = mimetypes.guess_type(row.file_name or path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=row.file_name or path.name,
        content_disposition_type="inline" if inline else "attachment",
    )
