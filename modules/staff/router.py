from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from core.permissions import STAFF_UPDATE, STAFF_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.staff.service import enter_staff, exit_staff, list_staff

router = APIRouter(tags=["Guard Staff"])


@router.get("/guard/staff")
def fetch_staff(
    search: str | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("name"),
    sortOrder: str | None = Query("asc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(STAFF_VIEW)),
):
    data = list_staff(
        db,
        current_user,
        search=search,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Staff fetched", data.model_dump(mode="json"))


@router.post("/guard/staff/{staff_id}/entry", status_code=status.HTTP_201_CREATED)
def staff_entry(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(STAFF_UPDATE)),
):
    item = enter_staff(db, current_user, staff_id)
    return success_response("Staff checked in", item.model_dump(mode="json"))


@router.post("/guard/staff/{staff_id}/exit")
def staff_exit(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(STAFF_UPDATE)),
):
    item = exit_staff(db, current_user, staff_id)
    return success_response("Staff checked out", item.model_dump(mode="json"))
