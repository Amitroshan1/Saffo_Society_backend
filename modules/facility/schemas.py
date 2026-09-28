from datetime import date

from pydantic import BaseModel, Field


class AmenityOut(BaseModel):
    id: int
    name: str
    open_time: str
    close_time: str


class SlotOut(BaseModel):
    start_time: str
    end_time: str
    is_booked: bool


class BookingCreate(BaseModel):
    amenity_id: int
    booking_date: date
    start_time: str
    end_time: str
    guest_count: int = Field(ge=1)
    purpose: str | None = None


class CancelIn(BaseModel):
    reason: str | None = None


class BookingOut(BaseModel):
    id: int
    amenity_id: int
    amenity_name: str
    booking_date: date
    start_time: str
    end_time: str
    guest_count: int
    purpose: str | None
    status: str
    cancel_reason: str | None = None