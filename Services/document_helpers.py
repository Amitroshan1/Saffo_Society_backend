"""Document helpers — lookups, numbering, permission resolution, serialization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.document import (
    Document,
    DocumentCategory,
    DocumentDownloadLog,
    DocumentPermission,
    DocumentVersion,
)
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.wing import Wing
from Schemas.document import DocumentPermissionIn
from Utils.audit import apply_create_audit, utcnow
from Utils.errors import ApiError

RESIDENT_VISIBLE_STATUSES = {"published", "expired"}


def require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def enforce_finance_scope(actor_role: str, scope: str) -> None:
    if actor_role == "finance" and scope != "finance":
        raise ApiError(403, "Finance role can only manage finance-scoped documents")


async def get_document_in_society(db: AsyncSession, document_id: UUID, society_id: UUID) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.society_id == society_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise ApiError(404, "Document not found")
    return document


async def get_category_in_society(
    db: AsyncSession, category_id: UUID, society_id: UUID
) -> DocumentCategory:
    result = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.id == category_id, DocumentCategory.society_id == society_id
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise ApiError(404, "Document category not found")
    return category


async def next_document_number(db: AsyncSession, society_id: UUID) -> str:
    count = (
        await db.execute(select(func.count()).where(Document.society_id == society_id))
    ).scalar_one()
    return f"DOC-{int(count) + 1:06d}"


async def get_active_permissions(db: AsyncSession, document_id: UUID) -> List[DocumentPermission]:
    rows = (
        await db.execute(
            select(DocumentPermission).where(
                DocumentPermission.document_id == document_id,
                DocumentPermission.is_active.is_(True),
            )
        )
    ).scalars().all()
    return list(rows)


async def validate_permissions(
    db: AsyncSession, permissions_in: Sequence[DocumentPermissionIn], *, society_id: UUID
) -> List[DocumentPermissionIn]:
    seen = set()
    validated: List[DocumentPermissionIn] = []
    for p in permissions_in:
        key = (p.permissionType, p.roleName, p.buildingId, p.wingId, p.flatId, p.residentId)
        if key in seen:
            raise ApiError(422, "Duplicate permission entries are not allowed")
        seen.add(key)

        if p.permissionType == "building":
            building = (
                await db.execute(
                    select(Building).where(Building.id == p.buildingId, Building.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not building:
                raise ApiError(404, f"Building not found: {p.buildingId}")
        elif p.permissionType == "wing":
            wing = (
                await db.execute(
                    select(Wing).where(Wing.id == p.wingId, Wing.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not wing:
                raise ApiError(404, f"Wing not found: {p.wingId}")
        elif p.permissionType == "flat":
            flat = (
                await db.execute(
                    select(Flat).where(Flat.id == p.flatId, Flat.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not flat:
                raise ApiError(404, f"Flat not found: {p.flatId}")
        elif p.permissionType == "resident":
            resident = (
                await db.execute(
                    select(Resident).where(Resident.id == p.residentId, Resident.society_id == society_id)
                )
            ).scalar_one_or_none()
            if not resident:
                raise ApiError(404, f"Resident not found: {p.residentId}")
        validated.append(p)
    return validated


def resolve_user_permissions(
    permissions: Sequence[DocumentPermission],
    *,
    role: str,
    resident_id: Optional[UUID] = None,
    building_ids: Optional[set] = None,
    wing_ids: Optional[set] = None,
    flat_ids: Optional[set] = None,
) -> tuple[bool, bool]:
    """Evaluate whether a non-admin actor can see/download a document.

    When no permission rows exist for a document, only admins may see it.
    Returns (is_visible, can_download).
    """
    if not permissions:
        return False, False

    visible = False
    can_download = False
    for p in permissions:
        matched = False
        if p.permission_type == "everyone":
            matched = True
        elif p.permission_type == "role" and p.role_name == role:
            matched = True
        elif p.permission_type == "building" and building_ids and p.building_id in building_ids:
            matched = True
        elif p.permission_type == "wing" and wing_ids and p.wing_id in wing_ids:
            matched = True
        elif p.permission_type == "flat" and flat_ids and p.flat_id in flat_ids:
            matched = True
        elif p.permission_type == "resident" and resident_id and p.resident_id == resident_id:
            matched = True

        if matched:
            visible = True
            if p.can_download:
                can_download = True
    return visible, can_download


async def get_role_visible_document_ids(
    db: AsyncSession, *, society_id: UUID, role: str
) -> set[UUID]:
    """Document ids visible to a non-scoped role (finance/guard) via 'everyone' or role permissions."""
    stmt = select(DocumentPermission.document_id).where(
        DocumentPermission.society_id == society_id,
        DocumentPermission.is_active.is_(True),
        or_(
            DocumentPermission.permission_type == "everyone",
            (DocumentPermission.permission_type == "role") & (DocumentPermission.role_name == role),
        ),
    ).distinct()
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def get_resident_visible_document_ids(
    db: AsyncSession,
    *,
    society_id: UUID,
    resident_id: UUID,
    occupancies: Sequence[Occupancy],
) -> set[UUID]:
    normal_occ = [o for o in occupancies if o.role != "domestic_help"]
    building_ids = {o.building_id for o in normal_occ}
    wing_ids = {o.wing_id for o in normal_occ}
    flat_ids = {o.flat_id for o in normal_occ}

    clauses = [
        DocumentPermission.permission_type == "everyone",
        (DocumentPermission.permission_type == "role") & (DocumentPermission.role_name == "resident"),
        (DocumentPermission.permission_type == "resident") & (DocumentPermission.resident_id == resident_id),
    ]
    if building_ids:
        clauses.append(
            (DocumentPermission.permission_type == "building")
            & (DocumentPermission.building_id.in_(building_ids))
        )
    if wing_ids:
        clauses.append(
            (DocumentPermission.permission_type == "wing") & (DocumentPermission.wing_id.in_(wing_ids))
        )
    if flat_ids:
        clauses.append(
            (DocumentPermission.permission_type == "flat") & (DocumentPermission.flat_id.in_(flat_ids))
        )

    stmt = (
        select(DocumentPermission.document_id)
        .where(
            DocumentPermission.society_id == society_id,
            DocumentPermission.is_active.is_(True),
            or_(*clauses),
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).scalars().all()
    return set(rows)


async def resolve_resident_context(
    db: AsyncSession, *, actor_id: UUID, society_id: UUID
) -> tuple[Resident, List[Occupancy]]:
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")

    occupancies = (
        await db.execute(
            select(Occupancy).where(
                Occupancy.society_id == society_id,
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not occupancies:
        raise ApiError(404, "Active occupancy not found for resident")
    return resident, list(occupancies)


async def log_download(
    db: AsyncSession,
    document: Document,
    *,
    actor_id: UUID,
    society_id: UUID,
    resident_id: Optional[UUID] = None,
    version_number: Optional[int] = None,
    ip_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    log = DocumentDownloadLog(
        document_id=document.id,
        society_id=society_id,
        user_id=actor_id,
        resident_id=resident_id,
        downloaded_at=utcnow(),
        ip_hash=ip_hash,
        user_agent=user_agent,
        version_number=version_number,
        metadata_json={},
    )
    db.add(log)
    document.download_count = (document.download_count or 0) + 1
    await db.commit()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def category_to_dict(category: DocumentCategory) -> Dict[str, Any]:
    return {
        "id": str(category.id),
        "societyId": str(category.society_id),
        "code": category.code,
        "name": category.name,
        "parentId": str(category.parent_id) if category.parent_id else None,
        "displayOrder": category.display_order,
        "description": category.description,
        "icon": category.icon,
        "isActive": category.is_active,
        "createdAt": category.created_at.isoformat() if category.created_at else None,
        "updatedAt": category.updated_at.isoformat() if category.updated_at else None,
    }


def permission_to_dict(permission: DocumentPermission) -> Dict[str, Any]:
    return {
        "id": str(permission.id),
        "documentId": str(permission.document_id),
        "permissionType": permission.permission_type,
        "roleName": permission.role_name,
        "buildingId": str(permission.building_id) if permission.building_id else None,
        "wingId": str(permission.wing_id) if permission.wing_id else None,
        "flatId": str(permission.flat_id) if permission.flat_id else None,
        "residentId": str(permission.resident_id) if permission.resident_id else None,
        "canDownload": permission.can_download,
        "isActive": permission.is_active,
    }


def version_to_dict(version: DocumentVersion) -> Dict[str, Any]:
    return {
        "id": str(version.id),
        "documentId": str(version.document_id),
        "versionNumber": version.version_number,
        "fileName": version.file_name,
        "fileUrl": version.file_url,
        "fileSizeBytes": version.file_size_bytes,
        "mimeType": version.mime_type,
        "changeNotes": version.change_notes,
        "uploadedBy": str(version.uploaded_by) if version.uploaded_by else None,
        "isLatest": version.is_latest,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
    }


def document_to_dict(
    document: Document,
    *,
    permissions: Optional[Sequence[DocumentPermission]] = None,
    versions: Optional[Sequence[DocumentVersion]] = None,
    category: Optional[DocumentCategory] = None,
    can_download: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": str(document.id),
        "societyId": str(document.society_id),
        "categoryId": str(document.category_id) if document.category_id else None,
        "categoryName": category.name if category else None,
        "title": document.title,
        "description": document.description,
        "fileName": document.file_name,
        "fileUrl": document.file_url,
        "fileSizeBytes": document.file_size_bytes,
        "mimeType": document.mime_type,
        "documentNumber": document.document_number,
        "status": document.status,
        "scope": document.scope,
        "tags": document.tags or [],
        "folderPath": document.folder_path,
        "expiresAt": document.expires_at.isoformat() if document.expires_at else None,
        "expiredAt": document.expired_at.isoformat() if document.expired_at else None,
        "archivedAt": document.archived_at.isoformat() if document.archived_at else None,
        "deletedAt": document.deleted_at.isoformat() if document.deleted_at else None,
        "isPinned": document.is_pinned,
        "isFavoriteDefault": document.is_favorite_default,
        "uploadedBy": str(document.uploaded_by) if document.uploaded_by else None,
        "publishedBy": str(document.published_by) if document.published_by else None,
        "publishedAt": document.published_at.isoformat() if document.published_at else None,
        "downloadCount": document.download_count,
        "viewCount": document.view_count,
        "metadata": document.metadata_json or {},
        "notes": document.notes,
        "isActive": document.is_active,
        "version": document.version,
        "createdAt": document.created_at.isoformat() if document.created_at else None,
        "updatedAt": document.updated_at.isoformat() if document.updated_at else None,
    }
    if permissions is not None:
        data["permissions"] = [permission_to_dict(p) for p in permissions]
    if versions is not None:
        data["versions"] = [version_to_dict(v) for v in versions]
    if can_download is not None:
        data["canDownload"] = can_download
    if is_favorite is not None:
        data["isFavorite"] = is_favorite
    return data
