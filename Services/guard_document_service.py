"""Guard document portal — list, get, download published documents."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.document import Document, DocumentCategory
from Schemas.common import build_pagination_meta
from Schemas.guard_document_schema import GuardDocumentListQueryParams
from Services.document_helpers import (
    document_to_dict,
    get_document_in_society,
    get_role_visible_document_ids,
    log_download,
    require_society_id,
)
from Utils.errors import ApiError


async def list_guard_documents(
    db: AsyncSession, query: GuardDocumentListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    visible_ids = await get_role_visible_document_ids(db, society_id=society_id, role="guard")
    if not visible_ids:
        return {"documents": [], "pagination": build_pagination_meta(query.page, query.page_size, 0)}

    base = select(Document).where(
        Document.society_id == society_id,
        Document.id.in_(visible_ids),
        Document.status == "published",
        Document.is_active.is_(True),
    )
    if query.category_id:
        base = base.where(Document.category_id == query.category_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(or_(Document.title.ilike(term), Document.document_number.ilike(term)))

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(Document.is_pinned.desc(), Document.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()

    category_ids = {d.category_id for d in rows if d.category_id}
    categories: Dict[UUID, DocumentCategory] = {}
    if category_ids:
        categories = {
            c.id: c
            for c in (
                await db.execute(select(DocumentCategory).where(DocumentCategory.id.in_(category_ids)))
            ).scalars().all()
        }

    return {
        "documents": [
            document_to_dict(d, category=categories.get(d.category_id) if d.category_id else None)
            for d in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_guard_document(
    db: AsyncSession, document_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.status != "published":
        raise ApiError(404, "Document not found")
    visible_ids = await get_role_visible_document_ids(db, society_id=society_id, role="guard")
    if document.id not in visible_ids:
        raise ApiError(404, "Document not found")
    return {"document": document_to_dict(document, can_download=True)}


async def guard_download_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.status != "published":
        raise ApiError(404, "Document not found")
    visible_ids = await get_role_visible_document_ids(db, society_id=society_id, role="guard")
    if document.id not in visible_ids:
        raise ApiError(404, "Document not found")

    await log_download(db, document, actor_id=actor_id, society_id=society_id)
    publish_simple(
        "DocumentDownloaded",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "role": "guard"},
    )
    return {"documentId": str(document.id), "fileUrl": document.file_url, "fileName": document.file_name}
