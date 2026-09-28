from pydantic import BaseModel


class VehicleCreate(BaseModel):
    vehicle_number: str
    vehicle_type: str
    make: str | None = None
    model: str | None = None
    color: str | None = None
    is_primary: bool = False


class VehicleUpdate(BaseModel):
    vehicle_number: str | None = None
    vehicle_type: str | None = None
    make: str | None = None
    model: str | None = None
    color: str | None = None
    is_primary: bool | None = None


class VehicleOut(BaseModel):
    id: int
    vehicle_number: str
    vehicle_type: str
    make: str | None
    model: str | None
    color: str | None
    is_primary: bool
    parking_code: str
    slot_id: int | None


class SlotOut(BaseModel):
    id: int
    code: str
    kind: str


class VisitorParkingCreate(BaseModel):
    vehicle_number: str
    vehicle_type: str
    purpose: str | None = None
    notes: str | None = None


class VisitorParkingOut(BaseModel):
    id: int
    vehicle_number: str
    vehicle_type: str
    purpose: str | None
    notes: str | None
    parking_code: str
    slot_id: int | None
    status: str