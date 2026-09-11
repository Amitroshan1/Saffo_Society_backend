"""Resident notice portal — wraps shared notice service."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from Schemas.resident_notice_schema import ResidentNoticeListQueryParams
from Services import notice_service


async def resident_list_notices(
    db: AsyncSession,
    query: ResidentNoticeListQueryParams,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
    view: Optional[str] = None,
) -> Dict[str, Any]:
    return await notice_service.resident_list_notices(
        db, query, actor_id=actor_id, actor_society_id=actor_society_id, view=view
    )


async def resident_get_notice(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notice_service.resident_get_notice(
        db, notice_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_mark_read(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notice_service.resident_mark_read(
        db, notice_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_acknowledge(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notice_service.resident_acknowledge(
        db, notice_id, actor_id=actor_id, actor_society_id=actor_society_id
    )


async def resident_list_attachments(
    db: AsyncSession, notice_id: UUID, *, actor_id: UUID, actor_society_id: UUID | None
) -> Dict[str, Any]:
    return await notice_service.resident_list_attachments(
        db, notice_id, actor_id=actor_id, actor_society_id=actor_society_id
    )
