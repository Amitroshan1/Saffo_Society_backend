from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from core.permissions import DOCUMENTS_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.document.service import get_document, list_documents, open_document

router = APIRouter(tags=["Guard Documents"])


@router.get("/guard/documents")
def fetch_documents(
    search: str | None = Query(None),
    category: str = Query("all"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("publishedAt"),
    sortOrder: str | None = Query("desc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DOCUMENTS_VIEW)),
):
    data = list_documents(
        db,
        current_user,
        search=search,
        category=category,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Documents fetched", data.model_dump(mode="json"))


@router.get("/guard/documents/{document_id}")
def fetch_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DOCUMENTS_VIEW)),
):
    item = get_document(db, current_user, document_id)
    return success_response("Document fetched", item.model_dump(mode="json"))


@router.get("/guard/documents/{document_id}/view")
def view_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DOCUMENTS_VIEW)),
) -> FileResponse:
    return open_document(db, current_user, document_id, inline=True)


@router.get("/guard/documents/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DOCUMENTS_VIEW)),
) -> FileResponse:
    return open_document(db, current_user, document_id, inline=False)
