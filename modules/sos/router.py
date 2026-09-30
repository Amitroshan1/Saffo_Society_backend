from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_resident
from modules.guard_sos.manager import broadcast_sos_created
from modules.guard_sos.service import created_payload
from modules.sos import service
from modules.sos.schemas import SosOut

router = APIRouter(prefix="/resident", tags=["Resident SOS"])


@router.post("/sos", response_model=SosOut, status_code=201)
async def create_sos(
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile | None = File(None),
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    saved = service.create_sos(db, ctx.user.id, ctx.society_id, title, description, file)
    society_id, payload = created_payload(db, saved["id"])
    await broadcast_sos_created(society_id, payload)
    return saved


@router.get("/sos", response_model=list[SosOut])
def list_sos(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_sos(db, ctx.user.id, ctx.society_id)


@router.post("/sos/{sos_id}/close", response_model=SosOut)
def close_sos(
    sos_id: int,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.close_sos(db, ctx.user.id, ctx.society_id, sos_id)