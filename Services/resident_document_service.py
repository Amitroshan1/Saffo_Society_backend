"""Resident document portal — wraps shared document service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.resident_document_schema import ResidentDocumentListQueryParams
from Services import document_service


async def list_resident_documents(
    db: AsyncSession,
    query: ResidentDocumentListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    return await document_service.list_resident_documents(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def get_resident_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await document_service.get_resident_document(
        db, document_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_download_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await document_service.resident_download_document(
        db, document_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def toggle_favorite(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await document_service.toggle_favorite(
        db, document_id, actor_id=actor_id, actor_society_id=actor_society_id
    )
