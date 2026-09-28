from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.notification.service import record
from modules.resident.service import _occupancy_or_404
from modules.vehicle.models import ParkingSlot, Vehicle, VisitorParking
from modules.vehicle.schemas import VehicleCreate, VehicleUpdate, VisitorParkingCreate


def _plate(value: str) -> str:
    plate = value.strip().upper().replace(" ", "")
    if len(plate) < 4:
        raise HTTPException(status_code=400, detail="Vehicle number is too short")
    return plate


def _vehicle_out(row: Vehicle) -> dict:
    return {
        "id": row.id,
        "vehicle_number": row.vehicle_number,
        "vehicle_type": row.vehicle_type,
        "make": row.make,
        "model": row.model,
        "color": row.color,
        "is_primary": row.is_primary,
        "parking_code": row.parking_code,
        "slot_id": row.slot_id,
    }


def _visitor_out(row: VisitorParking) -> dict:
    return {
        "id": row.id,
        "vehicle_number": row.vehicle_number,
        "vehicle_type": row.vehicle_type,
        "purpose": row.purpose,
        "notes": row.notes,
        "parking_code": row.parking_code,
        "slot_id": row.slot_id,
        "status": row.status,
    }


def _clear_primary(db: Session, occupancy_id: int) -> None:
    db.query(Vehicle).filter(
        Vehicle.occupancy_id == occupancy_id, Vehicle.is_primary == True
    ).update({"is_primary": False})


def _take_resident_slot(db: Session, society_id: int, occupancy_id: int) -> ParkingSlot:
    used = {
        row.slot_id
        for row in db.query(Vehicle.slot_id).filter(
            Vehicle.society_id == society_id, Vehicle.slot_id.isnot(None)
        )
    }
    mine = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == "resident",
            ParkingSlot.occupancy_id == occupancy_id,
            ParkingSlot.is_active == True,
        )
        .order_by(ParkingSlot.id.asc())
        .all()
    )
    for slot in mine:
        if slot.id not in used:
            return slot
    free = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == "resident",
            ParkingSlot.occupancy_id.is_(None),
            ParkingSlot.is_active == True,
        )
        .order_by(ParkingSlot.id.asc())
        .first()
    )
    if free:
        free.occupancy_id = occupancy_id
        db.flush()
        return free
    count = db.query(ParkingSlot).filter(ParkingSlot.society_id == society_id).count() + 1
    slot = ParkingSlot(
        society_id=society_id,
        occupancy_id=occupancy_id,
        code=f"P-{count:03d}",
        kind="resident",
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def list_slots(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.society_id == occupancy.society_id,
            ParkingSlot.occupancy_id == occupancy.id,
            ParkingSlot.is_active == True,
        )
        .order_by(ParkingSlot.code.asc())
        .all()
    )
    return [{"id": s.id, "code": s.code, "kind": s.kind} for s in rows]


def list_vehicles(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(Vehicle)
        .filter(Vehicle.occupancy_id == occupancy.id, Vehicle.society_id == occupancy.society_id)
        .order_by(Vehicle.is_primary.desc(), Vehicle.id.desc())
        .all()
    )
    return [_vehicle_out(r) for r in rows]


def create_vehicle(db: Session, user_id: int, society_id: int | None, data: VehicleCreate) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    plate = _plate(data.vehicle_number)
    exists = (
        db.query(Vehicle)
        .filter(Vehicle.society_id == occupancy.society_id, Vehicle.vehicle_number == plate)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Vehicle number already registered")
    slot = _take_resident_slot(db, occupancy.society_id, occupancy.id)
    make_primary = data.is_primary or (
        db.query(Vehicle).filter(Vehicle.occupancy_id == occupancy.id, Vehicle.is_primary == True).first()
        is None
    )
    if make_primary:
        _clear_primary(db, occupancy.id)
    row = Vehicle(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        slot_id=slot.id,
        vehicle_number=plate,
        vehicle_type=data.vehicle_type.strip().lower(),
        make=data.make,
        model=data.model,
        color=data.color,
        is_primary=make_primary,
        parking_code=slot.code,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _vehicle_out(row)


def update_vehicle(
    db: Session, user_id: int, society_id: int | None, vehicle_id: int, data: VehicleUpdate
) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    row = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
            Vehicle.occupancy_id == occupancy.id,
            Vehicle.society_id == occupancy.society_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if data.vehicle_number is not None:
        plate = _plate(data.vehicle_number)
        clash = (
            db.query(Vehicle)
            .filter(
                Vehicle.society_id == occupancy.society_id,
                Vehicle.vehicle_number == plate,
                Vehicle.id != row.id,
            )
            .first()
        )
        if clash:
            raise HTTPException(status_code=409, detail="Vehicle number already registered")
        row.vehicle_number = plate
    if data.vehicle_type is not None:
        row.vehicle_type = data.vehicle_type.strip().lower()
    if data.make is not None:
        row.make = data.make
    if data.model is not None:
        row.model = data.model
    if data.color is not None:
        row.color = data.color
    if data.is_primary is True:
        _clear_primary(db, occupancy.id)
        row.is_primary = True
    elif data.is_primary is False:
        row.is_primary = False
    db.commit()
    db.refresh(row)
    return _vehicle_out(row)


def _take_visitor_slot(db: Session, society_id: int) -> ParkingSlot:
    busy = {
        row.slot_id
        for row in db.query(VisitorParking.slot_id).filter(
            VisitorParking.society_id == society_id,
            VisitorParking.status == "active",
            VisitorParking.slot_id.isnot(None),
        )
    }
    free = (
        db.query(ParkingSlot)
        .filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.kind == "visitor",
            ParkingSlot.is_active == True,
        )
        .order_by(ParkingSlot.id.asc())
        .all()
    )
    for slot in free:
        if slot.id not in busy:
            return slot
    count = (
        db.query(ParkingSlot)
        .filter(ParkingSlot.society_id == society_id, ParkingSlot.kind == "visitor")
        .count()
        + 1
    )
    slot = ParkingSlot(
        society_id=society_id,
        occupancy_id=None,
        code=f"V-{count:03d}",
        kind="visitor",
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def request_visitor_parking(
    db: Session, user_id: int, society_id: int | None, data: VisitorParkingCreate
) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    slot = _take_visitor_slot(db, occupancy.society_id)
    row = VisitorParking(
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        slot_id=slot.id,
        vehicle_number=_plate(data.vehicle_number),
        vehicle_type=data.vehicle_type.strip().lower(),
        purpose=data.purpose,
        notes=data.notes,
        parking_code=slot.code,
        status="active",
    )
    db.add(row)
    db.flush()
    record(
        db,
        user_id=user_id,
        society_id=occupancy.society_id,
        occupancy_id=occupancy.id,
        category="parking",
        title="Visitor parking assigned",
        body=f"Parking code {row.parking_code} for {row.vehicle_number}",
    )
    db.commit()
    db.refresh(row)
    return _visitor_out(row)


def parking_history(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(VisitorParking)
        .filter(
            VisitorParking.occupancy_id == occupancy.id,
            VisitorParking.society_id == occupancy.society_id,
        )
        .order_by(VisitorParking.id.desc())
        .all()
    )
    return [_visitor_out(r) for r in rows]