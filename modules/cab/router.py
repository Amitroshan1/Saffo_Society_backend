from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.cab.service import (
    check_in_cab,
    create_cab,
    exit_cab,
    get_cab,
    list_cabs,
)

router = APIRouter(prefix="/guard/cabs", tags=["Guard Cabs"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_cab(
    vehicleNumber: str = Form(...),
    cabService: str = Form(...),
    building: str = Form(...),
    wing: str = Form(...),
    flat: str = Form(...),
    purpose: str = Form(...),
    driverName: str | None = Form(None),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = create_cab(
        db,
        current_user,
        vehicle_number=vehicleNumber,
        cab_service=cabService,
        building=building,
        wing=wing,
        flat=flat,
        purpose=purpose,
        driver_name=driverName,
        photo=photo,
    )
    return success_response("Cab logged", item.model_dump(mode="json"))


@router.get("")
def fetch_cabs(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = list_cabs(
        db,
        current_user,
        status_filter=status,
        search=search,
        page=page,
        page_size=pageSize,
        sort_by=sortBy,
        sort_order=sortOrder.lower(),
        date_from=dateFrom,
        date_to=dateTo,
    )
    return success_response("Guard cabs fetched", data.model_dump(mode="json"))


@router.get("/{cab_id}")
def fetch_cab(
    cab_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = get_cab(db, current_user, cab_id)
    return success_response("Cab fetched", item.model_dump(mode="json"))


@router.patch("/{cab_id}/check-in")
def mark_cab_check_in(
    cab_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = check_in_cab(db, current_user, cab_id)
    return success_response("Cab checked in", item.model_dump(mode="json"))


@router.patch("/{cab_id}/exit")
def mark_cab_exit(
    cab_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = exit_cab(db, current_user, cab_id)
    return success_response("Cab exited", item.model_dump(mode="json"))
