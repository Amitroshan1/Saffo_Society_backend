"""Document Management reports (Phase 12)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.document import Document, DocumentCategory, DocumentDownloadLog
from Models.resident import Resident
from Services.document_helpers import require_society_id
from Utils.errors import ApiError

REPORT_KEYS = {
    "by-category",
    "downloads",
    "most-viewed",
    "expired",
    "archived",
    "finance-docs",
    "resident-downloads",
    "storage-summary",
}


def _parse_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, f"Invalid {label} date") from exc


async def run_report(
    db: AsyncSession,
    report_key: str,
    *,
    actor_society_id: UUID | None,
    filters: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    key = report_key.strip().lower().replace("_", "-")
    if key not in REPORT_KEYS:
        raise ApiError(404, f"Unknown report: {report_key}")

    handlers = {
        "by-category": _by_category,
        "downloads": _downloads,
        "most-viewed": _most_viewed,
        "expired": _expired,
        "archived": _archived,
        "finance-docs": _finance_docs,
        "resident-downloads": _resident_downloads,
        "storage-summary": _storage_summary,
    }
    rows = await handlers[key](db, society_id, filters)
    return {"reportKey": key, "filters": {k: v for k, v in filters.items() if v}, "rows": rows}


async def _by_category(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(DocumentCategory.name, func.count(Document.id))
            .join(Document, Document.category_id == DocumentCategory.id)
            .where(Document.society_id == society_id, Document.status != "deleted")
            .group_by(DocumentCategory.name)
        )
    ).all()
    return [{"category": name, "count": int(cnt)} for name, cnt in rows]


async def _downloads(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = (
        select(DocumentDownloadLog, Document.title, Document.document_number)
        .join(Document, Document.id == DocumentDownloadLog.document_id)
        .where(DocumentDownloadLog.society_id == society_id)
    )
    if from_d:
        stmt = stmt.where(
            DocumentDownloadLog.downloaded_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc)
        )
    if to_d:
        stmt = stmt.where(
            DocumentDownloadLog.downloaded_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc)
        )
    rows = (await db.execute(stmt.order_by(DocumentDownloadLog.downloaded_at.desc()))).all()
    return [
        {
            "documentId": str(log.document_id),
            "documentTitle": title,
            "documentNumber": number,
            "userId": str(log.user_id),
            "residentId": str(log.resident_id) if log.resident_id else None,
            "downloadedAt": log.downloaded_at.isoformat(),
            "versionNumber": log.version_number,
        }
        for log, title, number in rows
    ]


async def _most_viewed(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Document)
            .where(Document.society_id == society_id, Document.status != "deleted")
            .order_by(Document.view_count.desc())
            .limit(20)
        )
    ).scalars().all()
    return [
        {
            "documentId": str(d.id),
            "documentNumber": d.document_number,
            "title": d.title,
            "viewCount": d.view_count,
            "downloadCount": d.download_count,
        }
        for d in rows
    ]


async def _expired(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = select(Document).where(Document.society_id == society_id, Document.status == "expired")
    if from_d:
        stmt = stmt.where(Document.expired_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc))
    if to_d:
        stmt = stmt.where(Document.expired_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc))
    rows = (await db.execute(stmt.order_by(Document.expired_at.desc()))).scalars().all()
    return [
        {
            "documentId": str(d.id),
            "documentNumber": d.document_number,
            "title": d.title,
            "expiredAt": d.expired_at.isoformat() if d.expired_at else None,
        }
        for d in rows
    ]


async def _archived(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = select(Document).where(Document.society_id == society_id, Document.status == "archived")
    if from_d:
        stmt = stmt.where(Document.archived_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc))
    if to_d:
        stmt = stmt.where(Document.archived_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc))
    rows = (await db.execute(stmt.order_by(Document.archived_at.desc()))).scalars().all()
    return [
        {
            "documentId": str(d.id),
            "documentNumber": d.document_number,
            "title": d.title,
            "archivedAt": d.archived_at.isoformat() if d.archived_at else None,
        }
        for d in rows
    ]


async def _finance_docs(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Document).where(
                Document.society_id == society_id,
                Document.scope == "finance",
                Document.status != "deleted",
            ).order_by(Document.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "documentId": str(d.id),
            "documentNumber": d.document_number,
            "title": d.title,
            "status": d.status,
            "downloadCount": d.download_count,
        }
        for d in rows
    ]


async def _resident_downloads(
    db: AsyncSession, society_id: UUID, filters: Dict[str, Optional[str]]
) -> List[dict]:
    from_d = _parse_date(filters.get("from"), "from")
    to_d = _parse_date(filters.get("to"), "to")
    stmt = (
        select(DocumentDownloadLog, Resident.name, Resident.code)
        .join(Resident, Resident.id == DocumentDownloadLog.resident_id)
        .where(
            DocumentDownloadLog.society_id == society_id,
            DocumentDownloadLog.resident_id.isnot(None),
        )
    )
    if from_d:
        stmt = stmt.where(
            DocumentDownloadLog.downloaded_at >= datetime.combine(from_d, time.min, tzinfo=timezone.utc)
        )
    if to_d:
        stmt = stmt.where(
            DocumentDownloadLog.downloaded_at <= datetime.combine(to_d, time.max, tzinfo=timezone.utc)
        )
    rows = (await db.execute(stmt.order_by(DocumentDownloadLog.downloaded_at.desc()))).all()
    return [
        {
            "documentId": str(log.document_id),
            "residentId": str(log.resident_id),
            "residentName": name,
            "residentCode": code,
            "downloadedAt": log.downloaded_at.isoformat(),
        }
        for log, name, code in rows
    ]


async def _storage_summary(
    db: AsyncSession, society_id: UUID, _filters: Dict[str, Optional[str]]
) -> List[dict]:
    rows = (
        await db.execute(
            select(Document.scope, func.coalesce(func.sum(Document.file_size_bytes), 0), func.count())
            .where(Document.society_id == society_id, Document.status != "deleted")
            .group_by(Document.scope)
        )
    ).all()
    return [
        {"scope": scope, "totalBytes": int(total_bytes), "documentCount": int(cnt)}
        for scope, total_bytes, cnt in rows
    ]
