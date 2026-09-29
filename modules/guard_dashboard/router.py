from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.guard_dashboard.service import get_dashboard

router = APIRouter(tags=["Guard Dashboard"])


@router.get("/guard/dashboard")
def fetch_dashboard(
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = get_dashboard(db, current_user)
    return success_response("Guard dashboard fetched", data.model_dump(mode="json"))
