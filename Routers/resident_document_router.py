"""Resident document portal routes — /api/v1/resident/documents/*."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.resident_document_list_query import get_resident_document_list_query
from Schemas.resident_document_schema import ResidentDocumentListQueryParams
from Services import resident_document_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["resident-documents"])


@router.get("/resident/documents")
async def resident_list_documents(
    query: ResidentDocumentListQueryParams = Depends(get_resident_document_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_document_service.list_resident_documents(
        db, query, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident documents fetched", data)


@router.get("/resident/documents/{document_id}")
async def resident_get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_document_service.get_resident_document(
        db, document_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident document fetched", data)


@router.get("/resident/documents/{document_id}/download")
async def resident_download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_document_service.resident_download_document(
        db, document_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Resident document download logged", data)


@router.post("/resident/documents/{document_id}/favorite")
async def resident_toggle_document_favorite(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("resident")),
):
    data = await resident_document_service.toggle_favorite(
        db, document_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Document favorite toggled", data)
