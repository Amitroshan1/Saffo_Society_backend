from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from core.permissions import MOVE_OUT_UPDATE, MOVE_OUT_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.move_out.service import allow_move_out, get_move_out, list_move_outs, open_move_out_file

router = APIRouter(tags=["Guard Move-out"])


@router.get("/guard/move-out")
def fetch_move_outs(
    search: str | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("moveOutDate"),
    sortOrder: str | None = Query("desc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(MOVE_OUT_VIEW)),
):
    data = list_move_outs(
        db,
        current_user,
        search=search,
        status_filter=status_filter,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Move-out clearance fetched", data.model_dump(mode="json"))


@router.get("/guard/move-out/{move_out_id}")
def fetch_move_out(
    move_out_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(MOVE_OUT_VIEW)),
):
    item = get_move_out(db, current_user, move_out_id)
    return success_response("Move-out fetched", item.model_dump(mode="json"))


@router.get("/guard/move-out/{move_out_id}/files/{file_id}")
def view_move_out_file(
    move_out_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(MOVE_OUT_VIEW)),
) -> FileResponse:
    return open_move_out_file(db, current_user, move_out_id, file_id)


@router.patch("/guard/move-out/{move_out_id}/allow")
def mark_move_out_allowed(
    move_out_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(MOVE_OUT_UPDATE)),
):
    item = allow_move_out(db, current_user, move_out_id)
    return success_response("Move-out allowed", item.model_dump(mode="json"))
