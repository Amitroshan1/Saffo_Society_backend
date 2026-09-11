"""Guard facility booking list query schema."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import Field

from Schemas.common import ListQueryParams


class GuardBookingListQueryParams(ListQueryParams):
    status: Optional[str] = None
    amenity_id: Optional[UUID] = Field(None, alias="amenityId")

    model_config = {"populate_by_name": True}
