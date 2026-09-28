from pydantic import BaseModel


class ProfileOut(BaseModel):
    full_name: str
    phone: str
    emergency_name: str | None
    emergency_phone: str | None


class ProfileUpdate(BaseModel):
    phone: str
    emergency_name: str | None = None
    emergency_phone: str | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class FlatOut(BaseModel):
    society_name: str
    building_name: str
    flat_number: str
    occupancy_id: int
    is_active: bool


class HouseholdMemberOut(BaseModel):
    id: int
    name: str
    relation: str | None
    phone: str | None

class GateVisitOut(BaseModel):
    id: int
    visitor_name: str
    visitor_phone: str
    status: str
    visitor_type: str
    purpose: str | None
    is_preapproved: bool


class GateDashboardOut(BaseModel):
    welcome: str
    flat: str
    pending_at_gate: list[GateVisitOut]
    upcoming_invites: list[GateVisitOut]
    active_sos: list = []
    todays_bookings: list = []
    primary_parking_code: str | None = None
    vehicles: list = []