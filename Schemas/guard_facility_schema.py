"""Guard facility booking list query schema."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import Field

from Schemas.common import ListQueryParams


class GuardBookingListQueryParams(ListQueryParams):
    status: Optional[str] = None
    amenity_id: Optional[UUID] = Field(None, alias="amenityId")
    from_date: Optional[date] = Field(None, alias="from")
    to_date: Optional[date] = Field(None, alias="to")
    booking_date: Optional[date] = Field(None, alias="date")

    model_config = {"populate_by_name": True}
