import math

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session, aliased, selectinload

from modules.clearance.models import Clearance
from modules.clearance.service import (
    ALL_CHECKS,
    NOT_ALL_CHECKS,
    STATUS_ALLOWED,
    allow_exit,
    checks_complete,
)
from modules.guard_common.deps import GuardUser
from modules.guard_move_out.schemas import (
    MoveOutCounts,
    MoveOutDocumentItem,
    MoveOutItem,
    MoveOutListData,
    Pagination,
)
from modules.resident.models import Building, Flat, Occupancy, Resident

STATUS_PENDING = "pending"
STATUS_READY = "ready"
STATUSES = ("all", STATUS_PENDING, STATUS_READY, STATUS_ALLOWED)

_ACTIVE = (Clearance.allowed_at.is_(None), Clearance.status == "open")


def _pagination(page: int, page_size: int, total: int) -> Pagination:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return Pagination(
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


def _direction(column, sort_order: str):
    if sort_order == "asc":
        return column.asc().nulls_last()
    return column.desc().nulls_last()


def guard_status(row: Clearance) -> str:
    if row.allowed_at is not None or row.status == STATUS_ALLOWED:
        return STATUS_ALLOWED
    if checks_complete(row):
        return STATUS_READY
    return STATUS_PENDING


def _documents(row: Clearance) -> list[MoveOutDocumentItem]:
    docs = sorted(row.documents or [], key=lambda item: item.id)
    return [
        MoveOutDocumentItem(id=doc.id, docType=doc.doc_type, fileUrl=doc.file_url) for doc in docs
    ]


def _to_item(row: Clearance) -> MoveOutItem:
    occupancy = row.occupancy
    flat = occupancy.flat
    have = {doc.doc_type for doc in (row.documents or [])}
    status_name = guard_status(row)
    return MoveOutItem(
        id=row.id,
        residentName=occupancy.resident.full_name,
        flatNo=flat.number,
        buildingNo=flat.building.name,
        moveOutDate=row.move_out_date,
        leaveLicense="leave_license" in have,
        tenantIdProof="tenant_id" in have,
        ownerConfirmation="owner_confirm" in have,
        duesClearance=bool(row.dues_clear),
        status=status_name,
        canAllow=status_name == STATUS_READY,
        allowedAt=row.allowed_at,
        documents=_documents(row),
    )


def _load_options():
    return (
        selectinload(Clearance.documents),
        selectinload(Clearance.occupancy).selectinload(Occupancy.resident),
        selectinload(Clearance.occupancy).selectinload(Occupancy.flat).selectinload(Flat.building),
    )


def _counts(db: Session, society_id: int) -> MoveOutCounts:
    base = db.query(Clearance).filter(Clearance.society_id == society_id)
    active = base.filter(*_ACTIVE)
    return MoveOutCounts(
        all=base.count(),
        pending=active.filter(NOT_ALL_CHECKS).count(),
        ready=active.filter(ALL_CHECKS).count(),
        allowed=base.filter(Clearance.allowed_at.isnot(None)).count(),
    )


def _apply_status(query, status_name: str):
    if status_name == STATUS_ALLOWED:
        return query.filter(Clearance.allowed_at.isnot(None))
    if status_name == STATUS_READY:
        return query.filter(*_ACTIVE, ALL_CHECKS)
    if status_name == STATUS_PENDING:
        return query.filter(*_ACTIVE, NOT_ALL_CHECKS)
    return query


def _case(db: Session, society_id: int, clearance_id: int) -> Clearance:
    row = (
        db.query(Clearance)
        .options(*_load_options())
        .filter(Clearance.id == clearance_id, Clearance.society_id == society_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Move-out not found")
    return row


def list_move_outs(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> MoveOutListData:
    page_size = min(page_size, 100)
    clean_status = (status_filter or "all").strip().lower()
    if clean_status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    order = (sort_order or "desc").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc"

    occupancy = aliased(Occupancy)
    resident = aliased(Resident)
    flat = aliased(Flat)
    building = aliased(Building)
    society_id = current_user.society_id
    query = (
        db.query(Clearance)
        .join(occupancy, Clearance.occupancy_id == occupancy.id)
        .join(resident, occupancy.resident_id == resident.id)
        .join(flat, occupancy.flat_id == flat.id)
        .join(building, flat.building_id == building.id)
        .options(*_load_options())
        .filter(Clearance.society_id == society_id)
    )
    query = _apply_status(query, clean_status)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((resident.full_name.ilike(term)) | (flat.number.ilike(term)))

    sorts = {
        "residentName": resident.full_name,
        "flatNo": flat.number,
        "buildingNo": building.name,
        "moveOutDate": Clearance.move_out_date,
        "allowedAt": Clearance.allowed_at,
    }
    if sort_by == "status":
        rank = case(
            (Clearance.allowed_at.isnot(None), 2),
            (ALL_CHECKS, 1),
            else_=0,
        )
        primary = rank.asc() if order == "asc" else rank.desc()
        query = query.order_by(primary, Clearance.move_out_date.desc().nulls_last(), Clearance.id.desc())
    else:
        column = sorts.get(sort_by, Clearance.move_out_date)
        query = query.order_by(_direction(column, order), Clearance.id.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return MoveOutListData(
        counts=_counts(db, society_id),
        items=[_to_item(row) for row in rows],
        pagination=_pagination(page, page_size, total),
    )


def get_move_out(db: Session, current_user: GuardUser, clearance_id: int) -> MoveOutItem:
    return _to_item(_case(db, current_user.society_id, clearance_id))


def allow_move_out(db: Session, current_user: GuardUser, clearance_id: int) -> MoveOutItem:
    allow_exit(db, current_user.society_id, clearance_id, current_user.id)
    return _to_item(_case(db, current_user.society_id, clearance_id))
