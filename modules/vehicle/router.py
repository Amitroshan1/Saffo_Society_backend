from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_resident
from modules.vehicle import service
from modules.vehicle.schemas import (
    SlotOut,
    VehicleCreate,
    VehicleOut,
    VehicleUpdate,
    VisitorParkingCreate,
    VisitorParkingOut,
)

router = APIRouter(prefix="/resident", tags=["Resident parking"])


@router.get("/parking", response_model=list[SlotOut])
def parking(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_slots(db, ctx.user.id, ctx.society_id)


@router.get("/parking/history", response_model=list[VisitorParkingOut])
def history(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.parking_history(db, ctx.user.id, ctx.society_id)


@router.get("/vehicles", response_model=list[VehicleOut])
def vehicles(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_vehicles(db, ctx.user.id, ctx.society_id)


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(
    data: VehicleCreate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.create_vehicle(db, ctx.user.id, ctx.society_id, data)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.update_vehicle(db, ctx.user.id, ctx.society_id, vehicle_id, data)


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vehicle(
    vehicle_id: int,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    service.delete_vehicle(db, ctx.user.id, ctx.society_id, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/visitor-parking/slots", response_model=list[SlotOut])
def free_visitor_slots(ctx: AuthContext = Depends(require_resident), db: Session = Depends(get_db)):
    return service.list_free_visitor_slots(db, ctx.user.id, ctx.society_id)


@router.post("/visitor-parking", response_model=VisitorParkingOut, status_code=201)
def visitor_parking(
    data: VisitorParkingCreate,
    ctx: AuthContext = Depends(require_resident),
    db: Session = Depends(get_db),
):
    return service.request_visitor_parking(db, ctx.user.id, ctx.society_id, data)