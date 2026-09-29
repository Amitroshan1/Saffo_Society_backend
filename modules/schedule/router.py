from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.schedule.schemas import PunchRequest
from modules.schedule.service import (
    list_attendance,
    list_punches,
    list_shifts,
    punch_in_shift,
    punch_out_shift,
)

router = APIRouter(tags=["Guard Schedule"])


@router.get("/guard/schedule/shifts")
def fetch_shifts(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("dutyDate"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_shifts(
        db,
        current_user,
        status_filter=status_filter,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder.lower(),
        date_from=dateFrom,
        date_to=dateTo,
    )
    return success_response("Guard shifts fetched", data.model_dump(mode="json"))


@router.get("/guard/schedule/attendance")
def fetch_attendance(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("dutyDate"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_attendance(
        db,
        current_user,
        status_filter=status_filter,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder.lower(),
        date_from=dateFrom,
        date_to=dateTo,
    )
    return success_response("Guard attendance fetched", data.model_dump(mode="json"))


@router.get("/guard/schedule/punches")
def fetch_punches(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("punchedAt"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_punches(
        db,
        current_user,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder.lower(),
        date_from=dateFrom,
        date_to=dateTo,
    )
    return success_response("Guard punch history fetched", data.model_dump(mode="json"))


@router.post("/guard/schedule/punch-in")
def mark_punch_in(
    body: PunchRequest,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = punch_in_shift(db, current_user, body.shiftId, body.latitude, body.longitude)
    return success_response("Punched in", item.model_dump(mode="json"))


@router.post("/guard/schedule/punch-out")
def mark_punch_out(
    body: PunchRequest,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = punch_out_shift(db, current_user, body.shiftId, body.latitude, body.longitude)
    return success_response("Punched out", item.model_dump(mode="json"))
