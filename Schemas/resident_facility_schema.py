"""Resident facility booking list query schema."""

from __future__ import annotations

from typing import Optional

from Schemas.common import ListQueryParams


class ResidentBookingListQueryParams(ListQueryParams):
    status: Optional[str] = None

    model_config = {"populate_by_name": True}
