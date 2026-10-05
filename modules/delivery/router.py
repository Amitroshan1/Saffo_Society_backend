from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from core.permissions import DELIVERIES_CREATE, DELIVERIES_UPDATE, DELIVERIES_VIEW
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.delivery.service import (
    check_in_delivery,
    collect_delivery,
    create_delivery,
    exit_delivery,
    get_delivery,
    hold_delivery,
    list_deliveries,
)

router = APIRouter(prefix="/guard/deliveries", tags=["Guard Deliveries"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_delivery(
    courierName: str = Form(...),
    phone: str = Form(...),
    company: str = Form(...),
    building: str = Form(...),
    wing: str = Form(...),
    flat: str = Form(...),
    trackingId: str | None = Form(None),
    parcelNote: str | None = Form(None),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DELIVERIES_CREATE)),
):
    item = create_delivery(
        db,
        current_user,
        courier_name=courierName,
        phone=phone,
        company=company,
        building=building,
        wing=wing,
        flat=flat,
        tracking_id=trackingId,
        parcel_note=parcelNote,
        photo=photo,
    )
    return success_response("Delivery logged", item.model_dump(mode="json"))


@router.get("")
def fetch_deliveries(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc"),
    dateFrom: date | None = Query(None, alias="from"),
    dateTo: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DELIVERIES_VIEW)),
):
    data = list_deliveries(
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
    return success_response("Guard deliveries fetched", data.model_dump(mode="json"))


@router.get("/{delivery_id}")
def fetch_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DELIVERIES_VIEW)),
):
    item = get_delivery(db, current_user, delivery_id)
    return success_response("Delivery fetched", item.model_dump(mode="json"))


@router.patch("/{delivery_id}/check-in")
def mark_delivery_check_in(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DELIVERIES_UPDATE)),
):
    item = check_in_delivery(db, current_user, delivery_id)
    return success_response("Delivery checked in", item.model_dump(mode="json"))


@router.patch("/{delivery_id}/exit")
def mark_delivery_exit(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard(DELIVERIES_UPDATE)),
):
    item = exit_delivery(db, current_user, delivery_id)
    return success_response("Delivery exited", item.model_dump(mode="json"))


@router.patch("/{delivery_id}/hold")
def mark_delivery_held(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = hold_delivery(db, current_user, delivery_id)
    return success_response("Delivery moved to gate", item.model_dump(mode="json"))


@router.patch("/{delivery_id}/collect")
def mark_delivery_collected(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = collect_delivery(db, current_user, delivery_id)
    return success_response("Delivery collected", item.model_dump(mode="json"))
