"""Resident document list query schema."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import Field

from Schemas.common import ListQueryParams


class ResidentDocumentListQueryParams(ListQueryParams):
    category_id: Optional[UUID] = Field(None, alias="categoryId")
    favorites_only: Optional[bool] = Field(None, alias="favoritesOnly")

    model_config = {"populate_by_name": True}
