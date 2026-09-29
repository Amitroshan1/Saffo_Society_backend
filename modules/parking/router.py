from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.parking.schemas import VisitorEntryRequest
from modules.parking.service import (
    enter_resident,
    enter_visitor,
    exit_resident,
    exit_visitor,
    list_parking_logs,
    list_resident_parking,
    list_visitor_parking,
)

router = APIRouter(tags=["Guard Parking"])


@router.get("/guard/parking/residents")
def fetch_resident_parking(
    search: str | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    building: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("building"),
    sortOrder: str | None = Query("asc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_resident_parking(
        db,
        current_user,
        search=search,
        status_filter=status_filter,
        building=building,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Resident parking fetched", data.model_dump(mode="json"))


@router.get("/guard/parking/visitors")
def fetch_visitor_parking(
    search: str | None = Query(None),
    status_filter: str = Query("all", alias="status"),
    building: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("slotNumber"),
    sortOrder: str | None = Query("asc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_visitor_parking(
        db,
        current_user,
        search=search,
        status_filter=status_filter,
        building=building,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Visitor parking fetched", data.model_dump(mode="json"))


@router.get("/guard/parking/logs")
def fetch_parking_logs(
    search: str | None = Query(None),
    parkingType: str = Query("all"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("entryTime"),
    sortOrder: str | None = Query("desc"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_parking_logs(
        db,
        current_user,
        search=search,
        parking_type=parkingType,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return success_response("Parking logs fetched", data.model_dump(mode="json"))


@router.post("/guard/parking/residents/{parking_id}/entry", status_code=status.HTTP_201_CREATED)
def resident_entry(
    parking_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = enter_resident(db, current_user, parking_id)
    return success_response("Resident vehicle entered", item.model_dump(mode="json"))


@router.post("/guard/parking/residents/{parking_id}/exit")
def resident_exit(
    parking_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = exit_resident(db, current_user, parking_id)
    return success_response("Resident vehicle exited", item.model_dump(mode="json"))


@router.post("/guard/parking/visitors/entry", status_code=status.HTTP_201_CREATED)
def visitor_entry(
    payload: VisitorEntryRequest,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = enter_visitor(db, current_user, payload)
    return success_response("Visitor vehicle entered", item.model_dump(mode="json"))


@router.post("/guard/parking/visitors/{log_id}/exit")
def visitor_exit(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = exit_visitor(db, current_user, log_id)
    return success_response("Visitor vehicle exited", item.model_dump(mode="json"))
