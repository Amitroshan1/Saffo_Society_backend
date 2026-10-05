from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_permission
from modules.sos import service
from modules.sos.schemas import SosCreate, SosOut
from core.permissions import SOS_CLOSE, SOS_CREATE, SOS_VIEW
router = APIRouter(prefix="/resident", tags=["Resident SOS"])


@router.post("/sos", response_model=SosOut, status_code=201)
def create_sos(
    data: SosCreate,
    ctx: AuthContext = Depends(require_permission(SOS_CREATE)),
    db: Session = Depends(get_db),
):
    return service.create_sos(db, ctx.user.id, ctx.society_id, data)


@router.get("/sos", response_model=list[SosOut])
def list_sos(ctx: AuthContext = Depends(require_permission(SOS_VIEW)), db: Session = Depends(get_db)):
    return service.list_sos(db, ctx.user.id, ctx.society_id)


@router.post("/sos/{sos_id}/close", response_model=SosOut)
def close_sos(
    sos_id: int,
    ctx: AuthContext = Depends(require_permission(SOS_CLOSE)),
    db: Session = Depends(get_db),
):
    return service.close_sos(db, ctx.user.id, ctx.society_id, sos_id)