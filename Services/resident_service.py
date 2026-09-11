"""Resident business logic."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.occupancy import Occupancy
from Models.resident import Resident
from Schemas.common import build_pagination_meta
from Schemas.occupancy import OccupancyOut
from Schemas.resident import ResidentCreate, ResidentListQueryParams, ResidentOut, ResidentUpdate
from Services.occupancy_helpers import (
    ensure_user_linkable,
    next_resident_code,
    sync_user_flat_for_resident,
)
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate
from Utils.validation_helpers import require_non_blank


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


async def _active_occupancies_for_resident(
    db: AsyncSession, resident_id: UUID
) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(Occupancy).where(
            Occupancy.resident_id == resident_id,
            Occupancy.status == "active",
        )
    )
    return [
        {
            "id": str(o.id),
            "flatId": str(o.flat_id),
            "role": o.role,
            "isPrimary": o.is_primary,
            "moveInDate": o.move_in_date.isoformat(),
        }
        for o in result.scalars().all()
    ]


async def _resident_dict(
    db: AsyncSession, resident: Resident, *, include_occupancies: bool = True
) -> Dict[str, Any]:
    occs = (
        await _active_occupancies_for_resident(db, resident.id) if include_occupancies else []
    )
    return ResidentOut.from_orm_resident(resident, current_occupancies=occs).model_dump(
        mode="json"
    )


async def create_resident(
    db: AsyncSession,
    body: ResidentCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    if body.userId:
        await ensure_user_linkable(db, body.userId, society_id)

    code = await next_resident_code(db, society_id)
    resident = Resident(
        society_id=society_id,
        user_id=body.userId,
        code=code,
        name=require_non_blank(body.name, "name"),
        email=str(body.email) if body.email else None,
        phone=body.phone,
        gender=body.gender,
        dob=body.dob,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(resident, actor_id)
    db.add(resident)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Resident code or user link conflict") from exc
    await db.refresh(resident)
    if resident.user_id:
        await sync_user_flat_for_resident(db, resident)
        await db.commit()
    return {"resident": await _resident_dict(db, resident)}


async def list_residents(
    db: AsyncSession,
    query: ResidentListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = ("name", "code", "created_at", "is_active")
    builder = (
        ListQueryBuilder(Resident)
        .filter_eq("society_id", society_id)
        .search(query.search, "name", "email", "phone", "code")
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="name")
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda r: r
    )
    serialized = [await _resident_dict(db, r) for r in items]
    return {
        "residents": serialized,
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_resident(
    db: AsyncSession,
    resident_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    resident = await _get_or_404(db, resident_id, society_id)
    return {"resident": await _resident_dict(db, resident)}


async def update_resident(
    db: AsyncSession,
    resident_id: UUID,
    body: ResidentUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    resident = await _get_or_404(db, resident_id, society_id)
    data = body.model_dump(exclude_unset=True)
    if "userId" in data and data["userId"]:
        await ensure_user_linkable(db, data["userId"], society_id, except_resident_id=resident.id)

    field_map = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "gender": "gender",
        "dob": "dob",
        "userId": "user_id",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            val = data[api_key]
            if api_key == "email" and val is not None:
                val = str(val)
            setattr(resident, orm_key, val)

    apply_update_audit(resident, actor_id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "User is already linked to another resident") from exc
    await db.refresh(resident)
    await sync_user_flat_for_resident(db, resident)
    await db.commit()
    await db.refresh(resident)
    return {"resident": await _resident_dict(db, resident)}


async def set_resident_active(
    db: AsyncSession,
    resident_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    resident = await _get_or_404(db, resident_id, society_id)
    if not active:
        active_occ = await db.execute(
            select(Occupancy).where(
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
            )
        )
        if active_occ.scalar_one_or_none():
            raise ApiError(422, "Cannot deactivate resident with active occupancies")

    if active:
        soft_activate(resident, actor_id)
    else:
        soft_deactivate(resident, actor_id)
    await db.commit()
    await db.refresh(resident)
    message = "Resident activated" if active else "Resident deactivated"
    return {
        "resident": await _resident_dict(db, resident),
        "message": message,
    }


async def _get_or_404(db: AsyncSession, resident_id: UUID, society_id: UUID) -> Resident:
    result = await db.execute(
        select(Resident).where(Resident.id == resident_id, Resident.society_id == society_id)
    )
    resident = result.scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")
    return resident
