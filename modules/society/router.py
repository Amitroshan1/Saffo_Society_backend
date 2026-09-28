from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_permission
from core.permissions import SOCIETIES_CREATE, SOCIETIES_VIEW
from modules.society import service
from modules.society.schemas import SocietyCreate, SocietyOut

router = APIRouter(prefix="/societies", tags=["Societies"])


@router.post("/", response_model=SocietyOut, status_code=201)
def create_society(
    data: SocietyCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_permission(SOCIETIES_CREATE)),
):
    return service.create_society_with_admin(db, data)


@router.get("/", response_model=list[SocietyOut])
def list_societies(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_permission(SOCIETIES_VIEW)),
):
    return service.list_societies(db)