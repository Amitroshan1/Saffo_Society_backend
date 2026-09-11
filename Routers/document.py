"""Document Management routes — admin/finance/guard/resident (Phase 12)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from Database.session import get_db
from Dependencies.auth import CurrentUser, require_roles
from Dependencies.document_list_query import (
    get_document_list_query,
    get_finance_document_list_query,
)
from Schemas.document import (
    DocumentCategoryCreate,
    DocumentCategoryUpdate,
    DocumentCreate,
    DocumentListQueryParams,
    DocumentPermissionsReplace,
    DocumentUpdate,
    DocumentVersionCreate,
    FinanceDocumentListQueryParams,
)
from Services import document_dashboard_service, document_report_service, document_service
from Utils.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["documents"])
ADMIN_FINANCE_ROLES = ("admin", "finance")


# ---------------------------------------------------------------------------
# Admin / finance — documents
# ---------------------------------------------------------------------------


@router.post("/documents")
async def create_document(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.create_document(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id, actor_role=current.role
    )
    return success_response(201, "Document created successfully", data)


@router.get("/documents")
async def list_documents(
    query: DocumentListQueryParams = Depends(get_document_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.list_documents(
        db, query, actor_society_id=current.society_id, actor_role=current.role
    )
    return success_response(200, "Documents fetched", data)


@router.get("/documents/dashboard")
async def documents_dashboard(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_dashboard_service.get_dashboard(db, actor_society_id=current.society_id)
    return success_response(200, "Document dashboard fetched", data)


@router.get("/documents/reports/{report_key}")
async def documents_report(
    report_key: str,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    data = await document_report_service.run_report(
        db,
        report_key,
        actor_society_id=current.society_id,
        filters={"from": from_date, "to": to_date},
    )
    return success_response(200, "Document report fetched", data)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.get_document(
        db, document_id, actor_society_id=current.society_id, actor_role=current.role
    )
    return success_response(200, "Document fetched", data)


@router.patch("/documents/{document_id}")
async def update_document(
    document_id: UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.update_document(
        db,
        document_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document updated successfully", data)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.soft_delete_document(
        db,
        document_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document deleted", data)


@router.post("/documents/{document_id}/archive")
async def archive_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.archive_document(
        db,
        document_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document archived", data)


@router.post("/documents/{document_id}/restore")
async def restore_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.restore_document(
        db,
        document_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document restored", data)


@router.post("/documents/{document_id}/publish")
async def publish_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.publish_document(
        db,
        document_id,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document published", data)


@router.put("/documents/{document_id}/permissions")
async def set_document_permissions(
    document_id: UUID,
    body: DocumentPermissionsReplace,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.set_permissions(
        db,
        document_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(200, "Document permissions updated", data)


@router.post("/documents/{document_id}/versions")
async def add_document_version(
    document_id: UUID,
    body: DocumentVersionCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.add_version(
        db,
        document_id,
        body,
        actor_id=current.user_id,
        actor_society_id=current.society_id,
        actor_role=current.role,
    )
    return success_response(201, "Document version added", data)


@router.get("/documents/{document_id}/versions")
async def list_document_versions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.list_versions(db, document_id, actor_society_id=current.society_id)
    return success_response(200, "Document versions fetched", data)


# ---------------------------------------------------------------------------
# Admin / finance — document categories
# ---------------------------------------------------------------------------


@router.post("/document-categories")
async def create_document_category(
    body: DocumentCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.create_category(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Document category created successfully", data)


@router.get("/document-categories")
async def list_document_categories(
    include_inactive: bool = Query(False, alias="includeInactive"),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.list_categories(
        db, actor_society_id=current.society_id, include_inactive=include_inactive
    )
    return success_response(200, "Document categories fetched", data)


@router.patch("/document-categories/{category_id}")
async def update_document_category(
    category_id: UUID,
    body: DocumentCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles(*ADMIN_FINANCE_ROLES)),
):
    data = await document_service.update_category(
        db, category_id, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Document category updated successfully", data)


@router.post("/document-categories/{category_id}/deactivate")
async def deactivate_document_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("admin")),
):
    data = await document_service.deactivate_category(
        db, category_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Document category deactivated", data)


# ---------------------------------------------------------------------------
# Finance portal
# ---------------------------------------------------------------------------


@router.get("/finance/documents")
async def finance_list_documents(
    query: FinanceDocumentListQueryParams = Depends(get_finance_document_list_query),
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await document_service.list_finance_documents(db, query, actor_society_id=current.society_id)
    return success_response(200, "Finance documents fetched", data)


@router.post("/finance/documents")
async def finance_upload_document(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await document_service.upload_finance_document(
        db, body, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(201, "Finance document uploaded successfully", data)


@router.get("/finance/documents/{document_id}")
async def finance_get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await document_service.get_finance_document(
        db, document_id, actor_society_id=current.society_id
    )
    return success_response(200, "Finance document fetched", data)


@router.get("/finance/documents/{document_id}/download")
async def finance_download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_roles("finance")),
):
    data = await document_service.finance_download_document(
        db, document_id, actor_id=current.user_id, actor_society_id=current.society_id
    )
    return success_response(200, "Finance document download logged", data)
