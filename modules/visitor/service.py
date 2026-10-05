import random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.guard_visitor.models import VISIT_APPROVED, VISIT_SCHEDULED
from modules.resident.service import _occupancy_or_404
from modules.visitor import crud
from modules.visitor.models import Visit
from modules.visitor.schemas import ApprovalIn, InvitationIn


def _to_out(visit: Visit) -> dict:
    return {
        "id": visit.id,
        "visitor_name": visit.visitor.name,
        "visitor_phone": visit.visitor.phone,
        "status": visit.status,
        "visitor_type": visit.visitor_type,
        "purpose": visit.purpose,
        "is_preapproved": visit.is_preapproved,
        "notes": visit.notes,
    }


def list_visitors(db, user_id, society_id, status, search) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = crud.list_visits(db, occupancy.id, occupancy.society_id, status, search)
    return [_to_out(v) for v in rows]


def invite(db: Session, user_id: int, society_id: int | None, data: InvitationIn) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    visitor = crud.get_or_create_visitor(
        db, occupancy.society_id, data.name.strip(), data.phone.strip()
    )
    visit = Visit(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        visitor_id=visitor.id,
        status=VISIT_SCHEDULED,
        visitor_type=data.visitor_type,
        purpose=data.purpose,
        is_preapproved=True,
        otp=f"{random.randint(0, 999999):06d}",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    visit.visitor = visitor
    return _to_out(visit)


def approve(db: Session, user_id: int, society_id: int | None, data: ApprovalIn) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    visit = crud.get_visit(db, data.visit_id, occupancy.id, occupancy.society_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    action = data.action.strip().lower()
    if action == "approve":
        visit.status = VISIT_APPROVED
        visit.is_preapproved = True
    elif action == "reject":
        visit.status = "rejected"
        visit.rejected_by = "Resident"
    elif action == "cancel":
        if visit.status != "scheduled":
            raise HTTPException(status_code=400, detail="Only scheduled invites can be cancelled")
        visit.status = "cancelled"
    else:
        raise HTTPException(status_code=400, detail="action must be approve, reject, or cancel")

    if data.notes:
        visit.notes = data.notes
    db.commit()
    db.refresh(visit)
    return _to_out(visit)