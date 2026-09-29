from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from modules.guard_common.deps import GuardUser, require_guard
from modules.guard_common.responses import success_response
from modules.guard_visitor.service import (
    check_in_visitor,
    create_visitor,
    exit_visitor,
    get_visitor,
    list_visitors,
    recent_visitors,
)

router = APIRouter(prefix="/guard/visitors", tags=["Guard Visitors"])


@router.post("", status_code=status.HTTP_201_CREATED)
def add_visitor(
    name: str = Form(...),
    phone: str = Form(...),
    purpose: str = Form(...),
    building: str = Form(...),
    wing: str | None = Form(None),
    flat: str = Form(...),
    personCount: int = Form(1),
    vehicleNumber: str | None = Form(None),
    vehicleType: str | None = Form(None),
    notifyResident: str | None = Form(None),
    preApproved: str | None = Form(None),
    remarks: str | None = Form(None),
    photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = create_visitor(
        db,
        current_user,
        name=name,
        phone=phone,
        purpose=purpose,
        building=building,
        wing=wing,
        flat=flat,
        person_count=personCount,
        vehicle_number=vehicleNumber,
        vehicle_type=vehicleType,
        notify_resident=notifyResident,
        pre_approved=preApproved,
        remarks=remarks,
        photo=photo,
    )
    return success_response("Visitor added", item.model_dump(mode="json"))


@router.get("")
def fetch_visitors(
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
    data = list_visitors(
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
    return success_response("Guard visitors fetched", data.model_dump(mode="json"))


@router.get("/recent")
def fetch_recent_visitors(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    data = recent_visitors(db, current_user, limit=limit)
    return success_response("Recent walk-ins fetched", data.model_dump(mode="json"))


@router.get("/{visit_id}")
def fetch_visitor(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = get_visitor(db, current_user, visit_id)
    return success_response("Visitor fetched", item.model_dump(mode="json"))


@router.patch("/{visit_id}/check-in")
def mark_visitor_check_in(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = check_in_visitor(db, current_user, visit_id)
    return success_response("Visitor checked in", item.model_dump(mode="json"))


@router.patch("/{visit_id}/exit")
def mark_visitor_exit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: GuardUser = Depends(require_guard),
):
    item = exit_visitor(db, current_user, visit_id)
    return success_response("Visitor exited", item.model_dump(mode="json"))
