import math
import re

from fastapi import HTTPException, status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from modules.guard_common.deps import GuardUser
from modules.resident.models import Building, Flat, Occupancy, Resident
from modules.vehicle.models import ParkingSlot, Vehicle

from .models import (
    RESIDENT_STATUSES,
    SLOT_RESIDENT,
    SLOT_VISITOR,
    STATUS_FREE,
    STATUS_INSIDE,
    STATUS_OCCUPIED,
    STATUS_OUTSIDE,
    STATUS_VACANT,
    VISITOR_STATUSES,
    ParkingLog,
    now_ist,
)
from .schemas import (
    Pagination,
    ParkingCounts,
    ParkingLogItem,
    ParkingLogListData,
    ResidentParkingItem,
    ResidentParkingListData,
    VisitorEntryRequest,
    VisitorParkingItem,
    VisitorParkingListData,
)

ALLOWED_VEHICLE_TYPES = {
    "car",
    "bike",
    "scooter",
    "ev",
    "commercial",
    "bicycle",
    "other",
}


def _digits_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _pagination(page: int, page_size: int, total: int) -> Pagination:
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return Pagination(
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


def _direction(column, sort_order: str):
    if sort_order == "asc":
        return column.asc().nulls_last()
    return column.desc().nulls_last()


def _has_vehicle(society_id: int):
    return exists().where(
        and_(Vehicle.slot_id == ParkingSlot.id, Vehicle.society_id == society_id)
    )


def _open_logs(society_id: int):
    return and_(
        ParkingLog.society_id == society_id,
        ParkingLog.exit_time.is_(None),
    )


def _chosen_vehicles(society_id: int):
    ranked = (
        select(
            Vehicle.slot_id.label("slot_id"),
            Vehicle.id.label("vehicle_id"),
            func.row_number()
            .over(
                partition_by=Vehicle.slot_id,
                order_by=(Vehicle.is_primary.desc(), Vehicle.id.asc()),
            )
            .label("rn"),
        )
        .where(Vehicle.society_id == society_id, Vehicle.slot_id.isnot(None))
        .subquery()
    )
    return select(ranked.c.slot_id, ranked.c.vehicle_id).where(ranked.c.rn == 1).subquery()


def _active_slots(db: Session, society_id: int, kind: str):
    return db.query(ParkingSlot).filter(
        ParkingSlot.society_id == society_id,
        ParkingSlot.kind == kind,
        ParkingSlot.is_active.is_(True),
    )


def _counts(db: Session, society_id: int) -> ParkingCounts:
    open_slot_ids = db.query(ParkingLog.parking_id).filter(_open_logs(society_id))
    assigned = _has_vehicle(society_id)
    residents = _active_slots(db, society_id, SLOT_RESIDENT)
    inside = residents.filter(assigned, ParkingSlot.id.in_(open_slot_ids)).count()
    outside = residents.filter(assigned, ~ParkingSlot.id.in_(open_slot_ids)).count()
    capacity = _active_slots(db, society_id, SLOT_VISITOR).count()
    filled = (
        db.query(ParkingLog)
        .filter(_open_logs(society_id), ParkingLog.parking_type == SLOT_VISITOR)
        .count()
    )
    return ParkingCounts(
        residentsInside=inside,
        residentsOutside=outside,
        visitorFilled=filled,
        visitorCapacity=capacity,
        visitorFree=max(0, capacity - filled),
    )


def _buildings(db: Session, society_id: int) -> list[str]:
    rows = (
        db.query(Building.name)
        .join(Flat, Flat.building_id == Building.id)
        .join(Occupancy, Occupancy.flat_id == Flat.id)
        .join(ParkingSlot, ParkingSlot.occupancy_id == Occupancy.id)
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == SLOT_RESIDENT,
            ParkingSlot.is_active.is_(True),
        )
        .distinct()
        .order_by(Building.name.asc())
        .all()
    )
    return [row[0] for row in rows]


def _resident_status(has_owner: bool, open_log: ParkingLog | None) -> str:
    if not has_owner:
        return STATUS_VACANT
    if open_log is not None:
        return STATUS_INSIDE
    return STATUS_OUTSIDE


def _to_resident(
    slot: ParkingSlot,
    vehicle: Vehicle | None,
    resident: Resident | None,
    flat: Flat | None,
    building: Building | None,
    open_log: ParkingLog | None,
) -> ResidentParkingItem:
    has_owner = vehicle is not None
    return ResidentParkingItem(
        id=slot.id,
        slotNumber=slot.code,
        building=building.name if building is not None else "",
        wingNo=None,
        status=_resident_status(has_owner, open_log),
        residentName=resident.full_name if has_owner and resident is not None else None,
        flatNo=flat.number if has_owner and flat is not None else None,
        vehicleNumber=vehicle.vehicle_number if has_owner else None,
        vehicleType=vehicle.vehicle_type if has_owner else None,
        entryTime=open_log.entry_time if open_log is not None else None,
    )


def _to_visitor(slot: ParkingSlot, open_log: ParkingLog | None) -> VisitorParkingItem:
    occupied = open_log is not None
    return VisitorParkingItem(
        id=slot.id,
        slotNumber=slot.code,
        building="",
        wingNo=None,
        status=STATUS_OCCUPIED if occupied else STATUS_FREE,
        logId=open_log.id if occupied else None,
        visitorName=open_log.visitor_name if occupied else None,
        phone=open_log.visitor_phone if occupied else None,
        flatBuilding=open_log.building if occupied else None,
        flatWingNo=open_log.wing_no if occupied else None,
        flatNo=open_log.flat_no if occupied else None,
        vehicleNumber=open_log.vehicle_number if occupied else None,
        vehicleType=open_log.vehicle_type if occupied else None,
        entryTime=open_log.entry_time if occupied else None,
    )


def _to_log(log: ParkingLog, slot: ParkingSlot | None) -> ParkingLogItem:
    return ParkingLogItem(
        id=log.id,
        parkingId=log.parking_id,
        slotNumber=slot.code if slot is not None else "",
        building=log.building,
        wingNo=log.wing_no,
        parkingType=log.parking_type,
        residentName=log.resident_name,
        visitorName=log.visitor_name,
        phone=log.visitor_phone,
        flatNo=log.flat_no,
        vehicleNumber=log.vehicle_number,
        vehicleType=log.vehicle_type,
        entryTime=log.entry_time,
        exitTime=log.exit_time,
        recordedBy=log.recorded_by,
    )


def _slot(db: Session, society_id: int, parking_id: int) -> ParkingSlot:
    slot = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.id == parking_id,
            ParkingSlot.society_id == society_id,
            ParkingSlot.is_active.is_(True),
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Parking slot not found")
    return slot


def _open_log_for(db: Session, society_id: int, parking_id: int) -> ParkingLog | None:
    return (
        db.query(ParkingLog)
        .filter(
            ParkingLog.society_id == society_id,
            ParkingLog.parking_id == parking_id,
            ParkingLog.exit_time.is_(None),
        )
        .first()
    )


def _vehicle_for(db: Session, society_id: int, slot_id: int) -> Vehicle | None:
    return (
        db.query(Vehicle)
        .filter(Vehicle.society_id == society_id, Vehicle.slot_id == slot_id)
        .order_by(Vehicle.is_primary.desc(), Vehicle.id.asc())
        .first()
    )


def _place(db: Session, occupancy_id: int | None):
    if occupancy_id is None:
        return None, None, None
    row = (
        db.query(Resident, Flat, Building)
        .select_from(Occupancy)
        .join(Resident, Resident.id == Occupancy.resident_id)
        .join(Flat, Flat.id == Occupancy.flat_id)
        .join(Building, Building.id == Flat.building_id)
        .filter(Occupancy.id == occupancy_id)
        .first()
    )
    if row is None:
        return None, None, None
    return row


def _resident_parts(db: Session, society_id: int, slot: ParkingSlot):
    vehicle = _vehicle_for(db, society_id, slot.id)
    occupancy_id = slot.occupancy_id or (vehicle.occupancy_id if vehicle is not None else None)
    resident, flat, building = _place(db, occupancy_id)
    return vehicle, resident, flat, building


def _apply_building(query, column, building: str | None):
    clean = (building or "").strip()
    if not clean or clean.lower() == "all":
        return query
    return query.filter(func.lower(column) == clean.lower())


def list_resident_parking(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    status_filter: str | None,
    building: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> ResidentParkingListData:
    page_size = min(page_size, 100)
    clean_status = (status_filter or "all").strip().lower()
    if clean_status not in RESIDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    order = (sort_order or "asc").strip().lower()
    if order not in ("asc", "desc"):
        order = "asc"

    society_id = current_user.society_id
    open_log = aliased(ParkingLog)
    chosen = _chosen_vehicles(society_id)
    assigned = Vehicle.id.isnot(None)
    query = (
        db.query(ParkingSlot, Vehicle, Resident, Flat, Building, open_log)
        .outerjoin(chosen, chosen.c.slot_id == ParkingSlot.id)
        .outerjoin(Vehicle, Vehicle.id == chosen.c.vehicle_id)
        .outerjoin(
            Occupancy,
            Occupancy.id == func.coalesce(ParkingSlot.occupancy_id, Vehicle.occupancy_id),
        )
        .outerjoin(Resident, Resident.id == Occupancy.resident_id)
        .outerjoin(Flat, Flat.id == Occupancy.flat_id)
        .outerjoin(Building, Building.id == Flat.building_id)
        .outerjoin(
            open_log,
            and_(
                open_log.parking_id == ParkingSlot.id,
                open_log.society_id == society_id,
                open_log.exit_time.is_(None),
            ),
        )
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == SLOT_RESIDENT,
            ParkingSlot.is_active.is_(True),
        )
    )
    query = _apply_building(query, Building.name, building)

    if clean_status == STATUS_VACANT:
        query = query.filter(~assigned)
    elif clean_status == STATUS_INSIDE:
        query = query.filter(assigned, open_log.id.isnot(None))
    elif clean_status == STATUS_OUTSIDE:
        query = query.filter(assigned, open_log.id.is_(None))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ParkingSlot.code.ilike(term),
                Resident.full_name.ilike(term),
                Vehicle.vehicle_number.ilike(term),
                Flat.number.ilike(term),
                Building.name.ilike(term),
            )
        )

    sorts = {
        "slotNumber": ParkingSlot.code,
        "building": Building.name,
        "residentName": Resident.full_name,
        "flatNo": Flat.number,
        "vehicleNumber": Vehicle.vehicle_number,
        "vehicleType": Vehicle.vehicle_type,
    }
    status_rank = case(
        (and_(assigned, open_log.id.isnot(None)), 0),
        (assigned, 1),
        else_=2,
    )
    if sort_by == "status":
        primary = status_rank.asc() if order == "asc" else status_rank.desc()
        query = query.order_by(primary, ParkingSlot.code.asc(), ParkingSlot.id.asc())
    elif sort_by == "entryTime":
        query = query.order_by(
            _direction(open_log.entry_time, order),
            ParkingSlot.code.asc(),
            ParkingSlot.id.asc(),
        )
    else:
        column = sorts.get(sort_by, Building.name)
        query = query.order_by(_direction(column, order), ParkingSlot.id.asc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return ResidentParkingListData(
        counts=_counts(db, society_id),
        buildings=_buildings(db, society_id),
        items=[_to_resident(*row) for row in rows],
        pagination=_pagination(page, page_size, total),
    )


def list_visitor_parking(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    status_filter: str | None,
    building: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> VisitorParkingListData:
    page_size = min(page_size, 100)
    clean_status = (status_filter or "all").strip().lower()
    if clean_status not in VISITOR_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    order = (sort_order or "asc").strip().lower()
    if order not in ("asc", "desc"):
        order = "asc"

    society_id = current_user.society_id
    open_log = aliased(ParkingLog)
    query = (
        db.query(ParkingSlot, open_log)
        .outerjoin(
            open_log,
            and_(
                open_log.parking_id == ParkingSlot.id,
                open_log.society_id == society_id,
                open_log.exit_time.is_(None),
            ),
        )
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == SLOT_VISITOR,
            ParkingSlot.is_active.is_(True),
        )
    )
    query = _apply_building(query, open_log.building, building)

    if clean_status == STATUS_OCCUPIED:
        query = query.filter(open_log.id.isnot(None))
    elif clean_status == STATUS_FREE:
        query = query.filter(open_log.id.is_(None))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ParkingSlot.code.ilike(term),
                open_log.visitor_name.ilike(term),
                open_log.visitor_phone.ilike(term),
                open_log.vehicle_number.ilike(term),
                open_log.flat_no.ilike(term),
                open_log.wing_no.ilike(term),
                open_log.building.ilike(term),
            )
        )

    visitor_sorts = {
        "slotNumber": ParkingSlot.code,
        "building": open_log.building,
        "visitorName": open_log.visitor_name,
        "vehicleNumber": open_log.vehicle_number,
        "entryTime": open_log.entry_time,
        "flatNo": open_log.flat_no,
    }
    if sort_by == "status":
        rank = case((open_log.id.isnot(None), 0), else_=1)
        primary = rank.asc() if order == "asc" else rank.desc()
        query = query.order_by(primary, ParkingSlot.code.asc(), ParkingSlot.id.asc())
    else:
        column = visitor_sorts.get(sort_by, ParkingSlot.code)
        query = query.order_by(_direction(column, order), ParkingSlot.id.asc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return VisitorParkingListData(
        counts=_counts(db, society_id),
        items=[_to_visitor(slot, log) for slot, log in rows],
        pagination=_pagination(page, page_size, total),
    )


def list_parking_logs(
    db: Session,
    current_user: GuardUser,
    *,
    search: str | None,
    parking_type: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str | None,
) -> ParkingLogListData:
    page_size = min(page_size, 100)
    clean_type = (parking_type or "all").strip().lower()
    if clean_type not in ("all", SLOT_RESIDENT, SLOT_VISITOR):
        raise HTTPException(status_code=400, detail="Invalid parking type")

    order = (sort_order or "desc").strip().lower()
    if order not in ("asc", "desc"):
        order = "desc"

    society_id = current_user.society_id
    query = (
        db.query(ParkingLog, ParkingSlot)
        .outerjoin(ParkingSlot, ParkingSlot.id == ParkingLog.parking_id)
        .filter(ParkingLog.society_id == society_id)
    )
    if clean_type != "all":
        query = query.filter(ParkingLog.parking_type == clean_type)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ParkingSlot.code.ilike(term),
                ParkingLog.vehicle_number.ilike(term),
                ParkingLog.resident_name.ilike(term),
                ParkingLog.visitor_name.ilike(term),
                ParkingLog.visitor_phone.ilike(term),
                ParkingLog.flat_no.ilike(term),
                ParkingLog.wing_no.ilike(term),
                ParkingLog.building.ilike(term),
            )
        )

    log_sorts = {
        "entryTime": ParkingLog.entry_time,
        "exitTime": ParkingLog.exit_time,
        "slotNumber": ParkingSlot.code,
        "vehicleNumber": ParkingLog.vehicle_number,
        "parkingType": ParkingLog.parking_type,
        "createdAt": ParkingLog.created_at,
        "residentName": ParkingLog.resident_name,
        "visitorName": ParkingLog.visitor_name,
    }
    column = log_sorts.get(sort_by, ParkingLog.entry_time)
    query = query.order_by(_direction(column, order), ParkingLog.id.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return ParkingLogListData(
        counts=_counts(db, society_id),
        items=[_to_log(log, slot) for log, slot in rows],
        pagination=_pagination(page, page_size, total),
    )


def enter_resident(
    db: Session,
    current_user: GuardUser,
    parking_id: int,
) -> ResidentParkingItem:
    society_id = current_user.society_id
    slot = _slot(db, society_id, parking_id)
    if slot.kind != SLOT_RESIDENT:
        raise HTTPException(status_code=400, detail="Resident parking slot is required")
    vehicle, resident, flat, building = _resident_parts(db, society_id, slot)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking slot is vacant")
    if _open_log_for(db, society_id, slot.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle is already inside")

    now = now_ist()
    log = ParkingLog(
        society_id=society_id,
        parking_id=slot.id,
        parking_type=SLOT_RESIDENT,
        resident_id=resident.id if resident is not None else None,
        resident_name=resident.full_name if resident is not None else None,
        building=building.name if building is not None else None,
        wing_no=None,
        flat_no=flat.number if flat is not None else None,
        vehicle_number=vehicle.vehicle_number,
        vehicle_type=vehicle.vehicle_type,
        entry_time=now,
        recorded_by=current_user.id,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _to_resident(slot, vehicle, resident, flat, building, log)


def exit_resident(
    db: Session,
    current_user: GuardUser,
    parking_id: int,
) -> ResidentParkingItem:
    society_id = current_user.society_id
    slot = _slot(db, society_id, parking_id)
    if slot.kind != SLOT_RESIDENT:
        raise HTTPException(status_code=400, detail="Resident parking slot is required")
    log = _open_log_for(db, society_id, slot.id)
    if not log or log.parking_type != SLOT_RESIDENT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle is already outside")

    log.exit_time = now_ist()
    db.commit()
    vehicle, resident, flat, building = _resident_parts(db, society_id, slot)
    return _to_resident(slot, vehicle, resident, flat, building, None)


def enter_visitor(
    db: Session,
    current_user: GuardUser,
    payload: VisitorEntryRequest,
) -> VisitorParkingItem:
    name = (payload.visitorName or "").strip()
    phone = _digits_phone(payload.phone)
    vehicle_number = (payload.vehicleNumber or "").strip().upper()
    vehicle_type = (payload.vehicleType or "").strip().lower()
    building = (payload.building or "").strip()
    wing = _clean(payload.wingNo)
    flat_no = (payload.flatNo or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Visitor name is required")
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Valid phone is required")
    if not vehicle_number:
        raise HTTPException(status_code=400, detail="Vehicle number is required")
    if vehicle_type not in ALLOWED_VEHICLE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid vehicle type")
    if not building:
        raise HTTPException(status_code=400, detail="Building number or name is required")
    if len(building) > 80:
        raise HTTPException(status_code=400, detail="Building number or name is too long")
    if wing and len(wing) > 30:
        raise HTTPException(status_code=400, detail="Wing number is too long")
    if not flat_no:
        raise HTTPException(status_code=400, detail="Visiting flat is required")

    slot = _slot(db, current_user.society_id, payload.parkingId)
    if slot.kind != SLOT_VISITOR:
        raise HTTPException(status_code=400, detail="Visitor parking slot is required")
    if _open_log_for(db, current_user.society_id, slot.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Visitor slot is already occupied")

    now = now_ist()
    log = ParkingLog(
        society_id=current_user.society_id,
        parking_id=slot.id,
        parking_type=SLOT_VISITOR,
        visitor_name=name,
        visitor_phone=phone,
        building=building,
        wing_no=wing,
        flat_no=flat_no,
        vehicle_number=vehicle_number,
        vehicle_type=vehicle_type,
        entry_time=now,
        recorded_by=current_user.id,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _to_visitor(slot, log)


def exit_visitor(
    db: Session,
    current_user: GuardUser,
    log_id: int,
) -> VisitorParkingItem:
    log = (
        db.query(ParkingLog)
        .filter(ParkingLog.id == log_id, ParkingLog.society_id == current_user.society_id)
        .first()
    )
    if not log or log.parking_type != SLOT_VISITOR:
        raise HTTPException(status_code=404, detail="Visitor parking entry not found")
    if log.exit_time is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Visitor vehicle has already exited")

    slot = _slot(db, current_user.society_id, log.parking_id)
    log.exit_time = now_ist()
    db.commit()
    return _to_visitor(slot, None)
