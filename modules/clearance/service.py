from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from modules.clearance.models import Clearance, ClearanceDocument
from modules.clearance.schemas import ClearanceCreate, DocumentCreate
from modules.resident.models import Flat, Occupancy
from modules.resident.service import _occupancy_or_404

RESIDENT_DOC_TYPES = {"leave_license", "tenant_id", "owner_confirm"}
DOC_TYPE_ALIASES = {
    "leave_license": "leave_license",
    "leavelicense": "leave_license",
    "tenant_id": "tenant_id",
    "tenantid": "tenant_id",
    "owner_confirm": "owner_confirm",
    "ownerconfirm": "owner_confirm",
    "dues_clear": "dues_clear",
    "duesclear": "dues_clear",
}


def _normalize_doc_type(value: str) -> str:
    return DOC_TYPE_ALIASES.get(value.strip().replace("-", "_").lower(), "")


def _out(row: Clearance) -> dict:
    docs = list(row.documents or [])
    have = {d.doc_type for d in docs}
    return {
        "id": row.id,
        "status": row.status,
        "dues_clear": row.dues_clear,
        "gate_allowed": row.dues_clear and RESIDENT_DOC_TYPES.issubset(have),
        "move_out_date": row.move_out_date,
        "documents": [
            {"id": d.id, "doc_type": d.doc_type, "file_url": d.file_url} for d in docs
        ],
    }


def _load(db: Session, clearance_id: int) -> Clearance | None:
    return (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(Clearance.id == clearance_id)
        .first()
    )


def list_mine(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(
            Clearance.occupancy_id == occupancy.id,
            Clearance.society_id == occupancy.society_id,
        )
        .order_by(Clearance.id.desc())
        .all()
    )
    return [_out(r) for r in rows]


def open_case(db: Session, user_id: int, society_id: int | None, data: ClearanceCreate) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    existing = (
        db.query(Clearance)
        .filter(
            Clearance.occupancy_id == occupancy.id,
            Clearance.society_id == occupancy.society_id,
            Clearance.status == "open",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An open move-out case already exists")
    row = Clearance(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        status="open",
        dues_clear=False,
        move_out_date=data.move_out_date,
    )
    db.add(row)
    db.commit()
    loaded = _load(db, row.id)
    return _out(loaded)


def add_document(
    db: Session, user_id: int, society_id: int | None, clearance_id: int, data: DocumentCreate
) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    doc_type = _normalize_doc_type(data.doc_type)
    if doc_type == "dues_clear":
        raise HTTPException(status_code=403, detail="Dues clearance is set by the office")
    if doc_type not in RESIDENT_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Unknown document type")
    file_url = data.file_url.strip()
    if not file_url:
        raise HTTPException(status_code=400, detail="file_url is required")
    row = (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(
            Clearance.id == clearance_id,
            Clearance.occupancy_id == occupancy.id,
            Clearance.society_id == occupancy.society_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Clearance not found")
    if row.status != "open":
        raise HTTPException(status_code=400, detail="Clearance is not open")
    current = next((d for d in row.documents if d.doc_type == doc_type), None)
    if current:
        current.file_url = file_url
    else:
        db.add(
            ClearanceDocument(
                clearance_id=row.id,
                society_id=row.society_id,
                doc_type=doc_type,
                file_url=file_url,
            )
        )
    db.commit()
    return _out(_load(db, row.id))


def mark_dues(db: Session, society_id: int | None, clearance_id: int) -> dict:
    if society_id is None:
        raise HTTPException(status_code=403, detail="No society selected")
    row = (
        db.query(Clearance)
        .options(joinedload(Clearance.documents))
        .filter(Clearance.id == clearance_id, Clearance.society_id == society_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Clearance not found")
    row.dues_clear = True
    db.commit()
    return _out(_load(db, row.id))


def list_for_guard(db: Session, society_id: int | None) -> list:
    if society_id is None:
        raise HTTPException(status_code=403, detail="No society selected")
    rows = (
        db.query(Clearance)
        .options(
            joinedload(Clearance.documents),
            joinedload(Clearance.occupancy).joinedload(Occupancy.flat).joinedload(Flat.building),
            joinedload(Clearance.occupancy).joinedload(Occupancy.resident),
        )
        .filter(Clearance.society_id == society_id)
        .order_by(Clearance.id.desc())
        .all()
    )
    result = []
    for row in rows:
        item = _out(row)
        flat = row.occupancy.flat
        item["flat"] = f"{flat.building.name}-{flat.number}"
        item["resident_name"] = row.occupancy.resident.full_name
        result.append(item)
    return result
