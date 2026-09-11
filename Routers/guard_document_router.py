"""Guard document portal routes — /api/v1/guard/documents/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.guard_document_list_query import get_guard_document_list_query
from Schemas.guard_document_schema import GuardDocumentListQueryParams
from Services import guard_document_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["guard-documents"])


@router.get("/guard/documents")
async def guard_list_documents(
    query: GuardDocumentListQueryParams = Depends(get_guard_document_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_document_service.list_guard_documents(
        db, query, actor_society_id=current.society_id
    )
    return success_response(200, "Guard documents fetched", data)


@router.get("/guard/documents/{document_id}")
async def guard_get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_document_service.get_guard_document(
        db, document_id, actor_society_id=current.society_id
    )
    return success_response(200, "Guard document fetched", data)


@router.get("/guard/documents/{document_id}/download")
async def guard_download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("guard")),
):
    data = await guard_document_service.guard_download_document(
        db, document_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Guard document download logged", data)
