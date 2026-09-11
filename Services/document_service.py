"""Document business logic — CRUD, lifecycle, categories, finance/guard/resident portals (Phase 12)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Events.bus import publish_simple
from Models.document import (
    Document,
    DocumentCategory,
    DocumentPermission,
    DocumentVersion,
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
    ResidentDocumentListQueryParams,
)
from Schemas.common import build_pagination_meta
from Services.document_helpers import (
    category_to_dict,
    document_to_dict,
    enforce_finance_scope,
    get_active_permissions,
    get_category_in_society,
    get_document_in_society,
    get_resident_visible_document_ids,
    log_download,
    next_document_number,
    require_society_id,
    resolve_resident_context,
    resolve_user_permissions,
    validate_permissions,
    version_to_dict,
)
from Utils.audit import apply_create_audit, apply_update_audit, utcnow
from Utils.errors import ApiError

FIELD_MAP = {
    "title": "title",
    "description": "description",
    "categoryId": "category_id",
    "fileName": "file_name",
    "fileUrl": "file_url",
    "fileSizeBytes": "file_size_bytes",
    "mimeType": "mime_type",
    "scope": "scope",
    "tags": "tags",
    "folderPath": "folder_path",
    "expiresAt": "expires_at",
    "isPinned": "is_pinned",
    "notes": "notes",
    "metadata": "metadata_json",
}
ACTIVE_STATUSES = ("draft", "published", "archived", "expired")


async def _create_permissions(
    db: AsyncSession,
    document: Document,
    permissions_in,
    *,
    actor_id: UUID,
    society_id: UUID,
) -> None:
    validated = await validate_permissions(db, permissions_in, society_id=society_id)
    for p in validated:
        row = DocumentPermission(
            document_id=document.id,
            society_id=society_id,
            permission_type=p.permissionType,
            role_name=p.roleName,
            building_id=p.buildingId,
            wing_id=p.wingId,
            flat_id=p.flatId,
            resident_id=p.residentId,
            can_download=p.canDownload,
            is_active=True,
            version=1,
        )
        apply_create_audit(row, actor_id)
        db.add(row)
    await db.flush()


# ---------------------------------------------------------------------------
# Admin / finance CRUD & lifecycle
# ---------------------------------------------------------------------------


async def create_document(
    db: AsyncSession,
    body: DocumentCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    if actor_role == "finance" and body.scope != "finance":
        raise ApiError(403, "Finance role can only create finance-scoped documents")

    if body.categoryId:
        await get_category_in_society(db, body.categoryId, society_id)

    document_number = await next_document_number(db, society_id)
    document = Document(
        society_id=society_id,
        category_id=body.categoryId,
        title=body.title,
        description=body.description,
        file_name=body.fileName,
        file_url=body.fileUrl,
        file_size_bytes=body.fileSizeBytes,
        mime_type=body.mimeType,
        document_number=document_number,
        status="draft",
        scope=body.scope,
        tags=body.tags,
        folder_path=body.folderPath,
        expires_at=body.expiresAt,
        is_pinned=body.isPinned,
        is_favorite_default=body.isFavoriteDefault,
        uploaded_by=actor_id,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(document, actor_id)
    db.add(document)
    await db.flush()

    if body.permissions:
        await _create_permissions(db, document, body.permissions, actor_id=actor_id, society_id=society_id)

    await db.commit()
    await db.refresh(document)

    publish_simple(
        "DocumentCreated",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "scope": document.scope},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def list_documents(
    db: AsyncSession,
    query: DocumentListQueryParams,
    *,
    actor_society_id: UUID | None,
    actor_role: Optional[str] = None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(Document).where(Document.society_id == society_id)

    if actor_role == "finance":
        base = base.where(Document.scope == "finance")
    elif query.scope:
        base = base.where(Document.scope == query.scope)

    if query.status:
        base = base.where(Document.status == query.status)
    else:
        base = base.where(Document.status != "deleted")
    if query.category_id:
        base = base.where(Document.category_id == query.category_id)
    if query.is_pinned is not None:
        base = base.where(Document.is_pinned == query.is_pinned)
    if query.is_active is not None:
        base = base.where(Document.is_active == query.is_active)
    if query.from_date:
        base = base.where(Document.created_at >= query.from_date)
    if query.to_date:
        base = base.where(Document.created_at <= query.to_date)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(
            or_(
                Document.title.ilike(term),
                Document.description.ilike(term),
                Document.document_number.ilike(term),
            )
        )

    allowed_sort = (
        "created_at",
        "updated_at",
        "title",
        "document_number",
        "status",
        "scope",
        "expires_at",
        "published_at",
    )
    sort_field = query.sort_by if query.sort_by in allowed_sort else "created_at"
    sort_col = getattr(Document, sort_field)
    base = base.order_by(sort_col.asc() if query.sort_order == "asc" else sort_col.desc())

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(base.offset((query.page - 1) * query.page_size).limit(query.page_size))
    ).scalars().all()

    return {
        "documents": [document_to_dict(d) for d in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_document(
    db: AsyncSession, document_id: UUID, *, actor_society_id: UUID | None, actor_role: Optional[str] = None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if actor_role == "finance":
        enforce_finance_scope(actor_role, document.scope)

    permissions = await get_active_permissions(db, document.id)
    versions = (
        await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
    ).scalars().all()
    category = None
    if document.category_id:
        category = (
            await db.execute(
                select(DocumentCategory).where(DocumentCategory.id == document.category_id)
            )
        ).scalar_one_or_none()

    return {
        "document": document_to_dict(
            document, permissions=permissions, versions=versions, category=category
        )
    }


async def update_document(
    db: AsyncSession,
    document_id: UUID,
    body: DocumentUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.status == "deleted":
        raise ApiError(422, "Document is deleted and cannot be updated")
    enforce_finance_scope(actor_role, document.scope)

    data = body.model_dump(exclude_unset=True)
    if "scope" in data and actor_role == "finance" and data["scope"] != "finance":
        raise ApiError(403, "Finance role cannot change scope away from finance")
    if "categoryId" in data and data["categoryId"]:
        await get_category_in_society(db, data["categoryId"], society_id)

    changed_fields = []
    for api_key, orm_key in FIELD_MAP.items():
        if api_key in data:
            setattr(document, orm_key, data[api_key])
            changed_fields.append(api_key)

    apply_update_audit(document, actor_id)
    await db.commit()

    if changed_fields:
        publish_simple(
            "DocumentUpdated",
            society_id=society_id,
            entity_type="document",
            entity_id=document.id,
            actor_id=actor_id,
            payload={"documentId": str(document.id), "changedFields": changed_fields},
        )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def publish_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)
    if document.status not in {"draft", "archived"}:
        raise ApiError(422, "Document cannot be published from current status")
    if not document.file_url:
        raise ApiError(422, "fileUrl is required to publish")

    document.status = "published"
    document.published_at = utcnow()
    document.published_by = actor_id
    document.archived_at = None
    document.expired_at = None
    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentUpdated",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "changedFields": ["status"], "status": "published"},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def archive_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)
    if document.status not in {"published", "expired"}:
        raise ApiError(422, "Only published or expired documents can be archived")

    document.status = "archived"
    document.archived_at = utcnow()
    if document.is_pinned:
        document.is_pinned = False
    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentArchived",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id)},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def restore_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)
    if document.status not in {"archived", "expired", "deleted"}:
        raise ApiError(422, "Document cannot be restored from current status")

    document.status = "published" if document.published_at else "draft"
    document.archived_at = None
    document.expired_at = None
    document.deleted_at = None
    document.is_active = True
    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentRestored",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "status": document.status},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def soft_delete_document(
    db: AsyncSession,
    document_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)
    if document.status == "deleted":
        raise ApiError(422, "Document is already deleted")

    document.status = "deleted"
    document.deleted_at = utcnow()
    document.is_active = False
    if document.is_pinned:
        document.is_pinned = False
    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentDeleted",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id)},
    )
    return {"documentId": str(document.id), "deleted": True}


async def set_permissions(
    db: AsyncSession,
    document_id: UUID,
    body: DocumentPermissionsReplace,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)

    existing = await get_active_permissions(db, document.id)
    for p in existing:
        p.is_active = False
        apply_update_audit(p, actor_id)

    if body.permissions:
        await _create_permissions(db, document, body.permissions, actor_id=actor_id, society_id=society_id)

    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentPermissionChanged",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "permissionCount": len(body.permissions)},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def add_version(
    db: AsyncSession,
    document_id: UUID,
    body: DocumentVersionCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    actor_role: str,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    enforce_finance_scope(actor_role, document.scope)
    if document.status == "deleted":
        raise ApiError(422, "Cannot add a version to a deleted document")

    last_version = (
        await db.execute(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document.id
            )
        )
    ).scalar_one()
    next_version_number = int(last_version or 0) + 1

    existing_latest = (
        await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id, DocumentVersion.is_latest.is_(True)
            )
        )
    ).scalars().all()
    for v in existing_latest:
        v.is_latest = False

    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_number,
        file_name=body.fileName,
        file_url=body.fileUrl,
        file_size_bytes=body.fileSizeBytes,
        mime_type=body.mimeType,
        change_notes=body.changeNotes,
        uploaded_by=actor_id,
        is_latest=True,
    )
    db.add(version)

    document.file_name = body.fileName
    document.file_url = body.fileUrl
    document.file_size_bytes = body.fileSizeBytes
    document.mime_type = body.mimeType or document.mime_type
    apply_update_audit(document, actor_id)
    await db.commit()

    publish_simple(
        "DocumentVersionCreated",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "versionNumber": next_version_number},
    )
    return await get_document(db, document.id, actor_society_id=society_id, actor_role=actor_role)


async def list_versions(
    db: AsyncSession, document_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    versions = (
        await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
    ).scalars().all()
    return {"versions": [version_to_dict(v) for v in versions]}


async def get_version(
    db: AsyncSession, document_id: UUID, version_number: int, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    version = (
        await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_number == version_number,
            )
        )
    ).scalar_one_or_none()
    if not version:
        raise ApiError(404, "Document version not found")
    return {"version": version_to_dict(version)}


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


async def create_category(
    db: AsyncSession, body: DocumentCategoryCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    existing = (
        await db.execute(
            select(DocumentCategory).where(
                DocumentCategory.society_id == society_id, DocumentCategory.code == body.code
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ApiError(409, f"Category code already exists: {body.code}")

    if body.parentId:
        await get_category_in_society(db, body.parentId, society_id)

    category = DocumentCategory(
        society_id=society_id,
        code=body.code,
        name=body.name,
        parent_id=body.parentId,
        display_order=body.displayOrder,
        description=body.description,
        icon=body.icon,
        metadata_json={},
        is_active=True,
        version=1,
    )
    apply_create_audit(category, actor_id)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return {"category": category_to_dict(category)}


async def list_categories(
    db: AsyncSession, *, actor_society_id: UUID | None, include_inactive: bool = False
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    stmt = select(DocumentCategory).where(DocumentCategory.society_id == society_id)
    if not include_inactive:
        stmt = stmt.where(DocumentCategory.is_active.is_(True))
    stmt = stmt.order_by(DocumentCategory.display_order.asc(), DocumentCategory.name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return {"categories": [category_to_dict(c) for c in rows]}


async def get_category(
    db: AsyncSession, category_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    category = await get_category_in_society(db, category_id, society_id)
    return {"category": category_to_dict(category)}


async def update_category(
    db: AsyncSession,
    category_id: UUID,
    body: DocumentCategoryUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    category = await get_category_in_society(db, category_id, society_id)

    data = body.model_dump(exclude_unset=True)
    if "parentId" in data and data["parentId"]:
        if data["parentId"] == category.id:
            raise ApiError(422, "Category cannot be its own parent")
        await get_category_in_society(db, data["parentId"], society_id)

    field_map = {
        "name": "name",
        "parentId": "parent_id",
        "displayOrder": "display_order",
        "description": "description",
        "icon": "icon",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(category, orm_key, data[api_key])

    apply_update_audit(category, actor_id)
    await db.commit()
    await db.refresh(category)
    return {"category": category_to_dict(category)}


async def deactivate_category(
    db: AsyncSession, category_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    category = await get_category_in_society(db, category_id, society_id)
    category.is_active = False
    apply_update_audit(category, actor_id)
    await db.commit()
    return {"categoryId": str(category.id), "isActive": False}


# ---------------------------------------------------------------------------
# Finance portal
# ---------------------------------------------------------------------------


async def list_finance_documents(
    db: AsyncSession, query: FinanceDocumentListQueryParams, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    base = select(Document).where(
        Document.society_id == society_id,
        Document.scope == "finance",
        Document.is_active.is_(True),
        Document.status != "deleted",
    )
    if query.status:
        base = base.where(Document.status == query.status)
    if query.category_id:
        base = base.where(Document.category_id == query.category_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(or_(Document.title.ilike(term), Document.document_number.ilike(term)))

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(Document.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()
    return {
        "documents": [document_to_dict(d) for d in rows],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def upload_finance_document(
    db: AsyncSession, body: DocumentCreate, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    body.scope = "finance"
    return await create_document(
        db, body, actor_id=actor_id, actor_society_id=actor_society_id, actor_role="finance"
    )


async def get_finance_document(
    db: AsyncSession, document_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.scope != "finance":
        raise ApiError(404, "Document not found")
    return await get_document(db, document.id, actor_society_id=society_id, actor_role="finance")


async def finance_download_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.scope != "finance" or document.status != "published":
        raise ApiError(404, "Document not found")
    await log_download(db, document, actor_id=actor_id, society_id=society_id)
    publish_simple(
        "DocumentDownloaded",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "role": "finance"},
    )
    return {"documentId": str(document.id), "fileUrl": document.file_url, "fileName": document.file_name}


# ---------------------------------------------------------------------------
# Resident portal
# ---------------------------------------------------------------------------


async def _resident_favorites(resident) -> set[str]:
    return set((resident.metadata_json or {}).get("favoriteDocuments", []))


async def list_resident_documents(
    db: AsyncSession,
    query: ResidentDocumentListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)

    visible_ids = await get_resident_visible_document_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if not visible_ids:
        return {"documents": [], "pagination": build_pagination_meta(query.page, query.page_size, 0)}

    favorites = await _resident_favorites(resident)
    if query.favorites_only:
        visible_ids = {i for i in visible_ids if str(i) in favorites}
        if not visible_ids:
            return {"documents": [], "pagination": build_pagination_meta(query.page, query.page_size, 0)}

    base = select(Document).where(
        Document.society_id == society_id,
        Document.id.in_(visible_ids),
        Document.status.in_(("published", "expired")),
        Document.is_active.is_(True),
    )
    if query.category_id:
        base = base.where(Document.category_id == query.category_id)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        base = base.where(or_(Document.title.ilike(term), Document.description.ilike(term)))

    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = (
        await db.execute(
            base.order_by(Document.is_pinned.desc(), Document.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).scalars().all()

    return {
        "documents": [
            document_to_dict(d, is_favorite=str(d.id) in favorites) for d in rows
        ],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_resident_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.status not in {"published", "expired"}:
        raise ApiError(404, "Document not found")

    visible_ids = await get_resident_visible_document_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if document.id not in visible_ids:
        raise ApiError(404, "Document not found")

    permissions = await get_active_permissions(db, document.id)
    building_ids = {o.building_id for o in occupancies}
    wing_ids = {o.wing_id for o in occupancies}
    flat_ids = {o.flat_id for o in occupancies}
    _, can_download = resolve_user_permissions(
        permissions,
        role="resident",
        resident_id=resident.id,
        building_ids=building_ids,
        wing_ids=wing_ids,
        flat_ids=flat_ids,
    )

    document.view_count = (document.view_count or 0) + 1
    await db.commit()
    await db.refresh(document)

    favorites = await _resident_favorites(resident)
    return {
        "document": document_to_dict(
            document, can_download=can_download, is_favorite=str(document.id) in favorites
        )
    }


async def resident_download_document(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    document = await get_document_in_society(db, document_id, society_id)
    if document.status not in {"published", "expired"}:
        raise ApiError(404, "Document not found")

    visible_ids = await get_resident_visible_document_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if document.id not in visible_ids:
        raise ApiError(404, "Document not found")

    permissions = await get_active_permissions(db, document.id)
    building_ids = {o.building_id for o in occupancies}
    wing_ids = {o.wing_id for o in occupancies}
    flat_ids = {o.flat_id for o in occupancies}
    _, can_download = resolve_user_permissions(
        permissions,
        role="resident",
        resident_id=resident.id,
        building_ids=building_ids,
        wing_ids=wing_ids,
        flat_ids=flat_ids,
    )
    if not can_download:
        raise ApiError(403, "You do not have permission to download this document")

    await log_download(db, document, actor_id=actor_id, society_id=society_id, resident_id=resident.id)
    publish_simple(
        "DocumentDownloaded",
        society_id=society_id,
        entity_type="document",
        entity_id=document.id,
        actor_id=actor_id,
        payload={"documentId": str(document.id), "role": "resident", "residentId": str(resident.id)},
    )
    return {"documentId": str(document.id), "fileUrl": document.file_url, "fileName": document.file_name}


async def toggle_favorite(
    db: AsyncSession, document_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    resident, occupancies = await resolve_resident_context(db, actor_id=actor_id, society_id=society_id)
    document = await get_document_in_society(db, document_id, society_id)

    visible_ids = await get_resident_visible_document_ids(
        db, society_id=society_id, resident_id=resident.id, occupancies=occupancies
    )
    if document.id not in visible_ids:
        raise ApiError(404, "Document not found")

    metadata = dict(resident.metadata_json or {})
    favorites = list(metadata.get("favoriteDocuments", []))
    doc_key = str(document.id)
    is_favorite: bool
    if doc_key in favorites:
        favorites.remove(doc_key)
        is_favorite = False
    else:
        favorites.append(doc_key)
        is_favorite = True
    metadata["favoriteDocuments"] = favorites
    resident.metadata_json = metadata
    apply_update_audit(resident, actor_id)
    await db.commit()

    return {"documentId": str(document.id), "isFavorite": is_favorite}
