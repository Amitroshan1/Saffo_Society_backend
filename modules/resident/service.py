from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from auth.models import User
from core.security import hash_password, verify_password
from modules.facility.models import Booking
from modules.resident import crud
from modules.resident.models import HouseholdMember
from modules.resident.schemas import ProfileUpdate
from modules.society.models import Society
from modules.sos.models import SosAlert
from modules.vehicle.models import Vehicle
from modules.visitor.models import Visit


def _occupancy_or_404(db: Session, user_id: int, society_id: int | None):
    if society_id is None:
        raise HTTPException(status_code=403, detail="No society selected")
    resident = crud.get_resident_by_user(db, user_id, society_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Active occupancy not found for resident")
    occupancy = crud.get_active_occupancy(db, resident.id, society_id)
    if not occupancy:
        raise HTTPException(status_code=404, detail="Active occupancy not found for resident")
    return resident, occupancy


def get_profile(db: Session, user_id: int, society_id: int | None) -> dict:
    resident, _ = _occupancy_or_404(db, user_id, society_id)
    return {
        "full_name": resident.full_name,
        "phone": resident.phone,
        "emergency_name": resident.emergency_name,
        "emergency_phone": resident.emergency_phone,
    }


def update_profile(db: Session, user_id: int, society_id: int | None, data: ProfileUpdate) -> dict:
    phone = data.phone.strip()
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Phone must stay valid — Guard Call uses it")
    resident, _ = _occupancy_or_404(db, user_id, society_id)
    resident.phone = phone
    resident.emergency_name = data.emergency_name
    resident.emergency_phone = data.emergency_phone
    db.commit()
    return get_profile(db, user_id, society_id)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> dict:
    if not verify_password(current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    user.password = hash_password(new_password)
    db.commit()
    return {"message": "Password updated"}


def get_flat(db: Session, user_id: int, society_id: int | None) -> dict:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    society = db.query(Society).filter(Society.id == occupancy.society_id).first()
    return {
        "society_name": society.name if society else "",
        "building_name": occupancy.flat.building.name,
        "flat_number": occupancy.flat.number,
        "occupancy_id": occupancy.id,
        "is_active": occupancy.is_active,
    }

def get_household(db: Session, user_id: int, society_id: int | None) -> list:
    _, occupancy = _occupancy_or_404(db, user_id, society_id)
    rows = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.occupancy_id == occupancy.id)
        .all()
    )
    return [
        {"id": m.id, "name": m.name, "relation": m.relation, "phone": m.phone}
        for m in rows
    ]

def _visit_card(visit: Visit) -> dict:
    return {
        "id": visit.id,
        "visitor_name": visit.visitor.name,
        "visitor_phone": visit.visitor.phone,
        "status": visit.status,
        "visitor_type": visit.visitor_type,
        "purpose": visit.purpose,
        "is_preapproved": visit.is_preapproved,
    }

def gate_dashboard(db: Session, user_id: int, society_id: int | None) -> dict:
    resident, occupancy = _occupancy_or_404(db, user_id, society_id)
    flat = get_flat(db, user_id, society_id)
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor))
        .filter(
            Visit.occupancy_id == occupancy.id,
            Visit.society_id == occupancy.society_id,
        )
        .order_by(Visit.id.desc())
        .all()
    )
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    open_sos = (
        db.query(SosAlert)
        .filter(
            SosAlert.occupancy_id == occupancy.id,
            SosAlert.society_id == occupancy.society_id,
            SosAlert.status == "open",
        )
        .order_by(SosAlert.id.desc())
        .all()
    )
    bookings = (
        db.query(Booking)
        .options(joinedload(Booking.amenity))
        .filter(
            Booking.occupancy_id == occupancy.id,
            Booking.society_id == occupancy.society_id,
            Booking.booking_date == today,
            Booking.status == "booked",
        )
        .order_by(Booking.start_time.asc())
        .all()
    )
    cars = (
        db.query(Vehicle)
        .filter(
            Vehicle.occupancy_id == occupancy.id,
            Vehicle.society_id == occupancy.society_id,
        )
        .order_by(Vehicle.is_primary.desc(), Vehicle.id.asc())
        .all()
    )
    primary = next((car.parking_code for car in cars if car.is_primary), None)
    return {
        "welcome": resident.full_name,
        "flat": f"{flat['building_name']}-{flat['flat_number']}",
        "pending_at_gate": [
            _visit_card(v) for v in visits if v.status == "waiting" and not v.is_preapproved
        ],
        "upcoming_invites": [_visit_card(v) for v in visits if v.status == "scheduled"],
        "active_sos": [
            {"id": row.id, "title": row.title, "status": row.status, "priority": row.priority}
            for row in open_sos
        ],
        "todays_bookings": [
            {
                "id": row.id,
                "amenity_name": row.amenity.name,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "status": row.status,
            }
            for row in bookings
        ],
        "primary_parking_code": primary,
        "vehicles": [
            {
                "id": car.id,
                "vehicle_number": car.vehicle_number,
                "vehicle_type": car.vehicle_type,
                "parking_code": car.parking_code,
                "is_primary": car.is_primary,
            }
            for car in cars
        ],
    }
