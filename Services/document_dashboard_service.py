"""Document Management dashboard KPIs (Phase 12)."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.document import Document, DocumentCategory
from Schemas.document import DOCUMENT_SCOPE_VALUES, DOCUMENT_STATUS_VALUES
from Services.document_helpers import document_to_dict, require_society_id


async def get_dashboard(db: AsyncSession, *, actor_society_id: UUID | None) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)

    async def _count(*clauses) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).where(Document.society_id == society_id, *clauses)
                )
            ).scalar_one()
        )

    by_status = []
    for status in DOCUMENT_STATUS_VALUES:
        cnt = await _count(Document.status == status)
        if cnt:
            by_status.append({"status": status, "count": cnt})

    by_scope = []
    for scope in DOCUMENT_SCOPE_VALUES:
        cnt = await _count(Document.scope == scope, Document.status != "deleted")
        if cnt:
            by_scope.append({"scope": scope, "count": cnt})

    category_rows = (
        await db.execute(
            select(DocumentCategory.name, func.count(Document.id))
            .join(Document, Document.category_id == DocumentCategory.id)
            .where(Document.society_id == society_id, Document.status != "deleted")
            .group_by(DocumentCategory.name)
        )
    ).all()
    by_category = [{"category": name, "count": int(cnt)} for name, cnt in category_rows]

    total_active = await _count(Document.status != "deleted")
    published_count = await _count(Document.status == "published")
    pinned_count = await _count(Document.is_pinned.is_(True), Document.status != "deleted")

    storage_row = (
        await db.execute(
            select(func.coalesce(func.sum(Document.file_size_bytes), 0), func.count())
            .where(Document.society_id == society_id, Document.status != "deleted")
        )
    ).first()
    storage_bytes_total = int(storage_row[0]) if storage_row else 0
    storage_doc_count = int(storage_row[1]) if storage_row else 0

    recent_rows = (
        await db.execute(
            select(Document)
            .where(Document.society_id == society_id, Document.status != "deleted")
            .order_by(Document.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    top_downloaded = (
        await db.execute(
            select(Document)
            .where(Document.society_id == society_id, Document.status != "deleted")
            .order_by(Document.download_count.desc())
            .limit(5)
        )
    ).scalars().all()

    return {
        "totalDocuments": total_active,
        "publishedCount": published_count,
        "pinnedCount": pinned_count,
        "byStatus": by_status,
        "byScope": by_scope,
        "byCategory": by_category,
        "storageSummary": {
            "totalBytes": storage_bytes_total,
            "documentCount": storage_doc_count,
        },
        "recentUploads": [document_to_dict(d) for d in recent_rows],
        "topDownloaded": [document_to_dict(d) for d in top_downloaded],
    }
