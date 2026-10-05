from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_permission
from core.permissions import CLEARANCE_CREATE, CLEARANCE_DUES, CLEARANCE_VIEW, MOVE_OUT_VIEW
from modules.clearance import service
from modules.clearance.schemas import (
    ClearanceCreate,
    ClearanceOut,
    DocumentCreate,
    GuardClearanceOut,
)
from modules.guard_common.deps import GuardUser, require_guard

router = APIRouter(tags=["Clearance"])


@router.get("/resident/clearances", response_model=list[ClearanceOut])
def my_clearances(
    ctx: AuthContext = Depends(require_permission(CLEARANCE_VIEW)),
    db: Session = Depends(get_db),
):
    return service.list_mine(db, ctx.user.id, ctx.society_id)


@router.post("/resident/clearances", response_model=ClearanceOut, status_code=201)
def open_clearance(
    data: ClearanceCreate,
    ctx: AuthContext = Depends(require_permission(CLEARANCE_CREATE)),
    db: Session = Depends(get_db),
):
    return service.open_case(db, ctx.user.id, ctx.society_id, data)


@router.post("/resident/clearances/{clearance_id}/documents", response_model=ClearanceOut)
def upload_document(
    clearance_id: int,
    data: DocumentCreate,
    ctx: AuthContext = Depends(require_permission(CLEARANCE_CREATE)),
    db: Session = Depends(get_db),
):
    return service.add_document(db, ctx.user.id, ctx.society_id, clearance_id, data)


@router.post("/clearances/{clearance_id}/dues", response_model=ClearanceOut)
def mark_dues(
    clearance_id: int,
    ctx: AuthContext = Depends(require_permission(CLEARANCE_DUES)),
    db: Session = Depends(get_db),
):
    return service.mark_dues(db, ctx.society_id, clearance_id)


@router.get("/guard/clearances", response_model=list[GuardClearanceOut])
def guard_clearances(
    current_user: GuardUser = Depends(require_guard(MOVE_OUT_VIEW)),
    db: Session = Depends(get_db),
):
    return service.list_for_guard(db, current_user.society_id)
