from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.residents import search_flats
from modules.guard_common.responses import success_response

router = APIRouter(tags=["Guard Flats"])


@router.get("/guard/flats")
def fetch_flats(
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    items = search_flats(db, current_user, search)
    return success_response(
        "Flats fetched successfully",
        [item.model_dump(mode="json") for item in items],
    )
