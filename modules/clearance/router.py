from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, get_current_user, require_resident
from core.exceptions import forbidden
from modules.clearance import service
from modules.clearance.schemas import (
    ClearanceCreate,
    ClearanceOut,
    GuardClearanceOut,
)

router = APIRouter(tags=["Clearance"])


@router.get("/resident/clearances", response_model=list[ClearanceOut])
def my_clearances(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_mine(db, ctx.user.id, ctx.society_id)


@router.post("/resident/clearances", response_model=ClearanceOut, status_code=201)
def open_clearance(
    data: ClearanceCreate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.open_case(db, ctx.user.id, ctx.society_id, data)


@router.post("/resident/clearances/{clearance_id}/documents", response_model=ClearanceOut)
def upload_document(
    clearance_id: int,
    data: DocumentCreate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.add_document(
        db, ctx.user.id, ctx.society_id, clearance_id, file, doc_type
    )


@router.post("/clearances/{clearance_id}/dues", response_model=ClearanceOut)
def mark_dues(
    clearance_id: int,
    ctx: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if ctx.role_name != "admin":
        raise forbidden("Admin role required")
    return service.mark_dues(db, ctx.society_id, clearance_id)


@router.get("/guard/clearances", response_model=list[GuardClearanceOut])
def guard_clearances(ctx: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    if ctx.role_name != "security_guard":
        raise forbidden("Guard role required")
    return service.list_for_guard(db, ctx.society_id)
