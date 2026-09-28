from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_resident
from modules.visitor import service
from modules.visitor.schemas import ApprovalIn, InvitationIn, VisitOut

router = APIRouter(prefix="/resident", tags=["Resident visitors"])


@router.get("/visitors", response_model=list[VisitOut])
def list_visitors(
    status: str | None = Query(None),
    search: str | None = Query(None),
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.list_visitors(db, ctx.user.id, ctx.society_id, status, search)


@router.post("/visitor-invitations", response_model=VisitOut, status_code=201)
def invite(
    data: InvitationIn,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.invite(db, ctx.user.id, ctx.society_id, data)


@router.post("/visitor-approval", response_model=VisitOut)
def approval(
    data: ApprovalIn,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.approve(db, ctx.user.id, ctx.society_id, data)