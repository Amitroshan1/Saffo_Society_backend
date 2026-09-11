"""Resident notice list query schema."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from Schemas.common import ListQueryParams


class ResidentNoticeListQueryParams(ListQueryParams):
    category: Optional[str] = None
    priority: Optional[str] = None
    unread_only: Optional[bool] = Field(None, alias="unreadOnly")
    view: Optional[str] = None  # inbox | pinned | unread | archive

    model_config = {"populate_by_name": True}
