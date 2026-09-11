"""Guard document list query schema."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import Field

from Schemas.common import ListQueryParams


class GuardDocumentListQueryParams(ListQueryParams):
    category_id: Optional[UUID] = Field(None, alias="categoryId")

    model_config = {"populate_by_name": True}
