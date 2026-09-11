"""Visitor identity business logic."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.visit import Visit
from Models.visitor import Visitor
from Schemas.common import build_pagination_meta
from Schemas.visitor import VisitorCreate, VisitorListQueryParams, VisitorOut, VisitorUpdate
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


OPEN_VISIT_STATUSES = ("scheduled", "waiting", "approved", "checked_in")


def _require_society_id(actor_society_id: UUID | None) -> UUID:
    if not actor_society_id:
        raise ApiError(400, "User is not linked to a society")
    return actor_society_id


def _visitor_dict(visitor: Visitor) -> Dict[str, Any]:
    return VisitorOut.from_orm_visitor(visitor).model_dump(mode="json")


async def create_visitor(
    db: AsyncSession,
    body: VisitorCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    if (body.governmentIdType and not body.governmentIdNumber) or (
        body.governmentIdNumber and not body.governmentIdType
    ):
        raise ApiError(422, "governmentIdType and governmentIdNumber must be provided together")

    visitor = Visitor(
        society_id=society_id,
        name=body.name,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        photo_url=body.photoUrl,
        government_id_type=body.governmentIdType,
        government_id_number=body.governmentIdNumber,
        metadata_json=body.metadata,
        notes=body.notes,
        is_active=True,
        version=1,
    )
    apply_create_audit(visitor, actor_id)
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)
    return {"visitor": _visitor_dict(visitor)}


async def list_visitors(
    db: AsyncSession,
    query: VisitorListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    allowed_sort = ("name", "phone", "created_at", "is_active")
    builder = (
        ListQueryBuilder(Visitor)
        .filter_eq("society_id", society_id)
        .search(
            query.search,
            "name",
            "phone",
            "email",
            "government_id_number",
        )
        .filter_eq("phone", query.phone)
        .filter_eq("government_id_type", query.government_id_type)
        .filter_eq("is_active", query.is_active)
        .sort(query.sort_by, query.sort_order, allowed_sort, default="name")
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda v: v
    )
    return {
        "visitors": [_visitor_dict(v) for v in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_visitor(
    db: AsyncSession,
    visitor_id: UUID,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    visitor = await _get_or_404(db, visitor_id, _require_society_id(actor_society_id))
    return {"visitor": _visitor_dict(visitor)}


async def update_visitor(
    db: AsyncSession,
    visitor_id: UUID,
    body: VisitorUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visitor = await _get_or_404(db, visitor_id, society_id)
    data = body.model_dump(exclude_unset=True)
    if ("governmentIdType" in data) ^ ("governmentIdNumber" in data):
        # allow partial update only if other side already exists on record
        final_type = data.get("governmentIdType", visitor.government_id_type)
        final_num = data.get("governmentIdNumber", visitor.government_id_number)
        if bool(final_type) != bool(final_num):
            raise ApiError(422, "governmentIdType and governmentIdNumber must be provided together")

    field_map = {
        "name": "name",
        "phone": "phone",
        "email": "email",
        "photoUrl": "photo_url",
        "governmentIdType": "government_id_type",
        "governmentIdNumber": "government_id_number",
        "metadata": "metadata_json",
        "notes": "notes",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            val = data[api_key]
            if api_key == "email" and val is not None:
                val = str(val)
            setattr(visitor, orm_key, val)

    apply_update_audit(visitor, actor_id)
    await db.commit()
    await db.refresh(visitor)
    return {"visitor": _visitor_dict(visitor)}


async def set_visitor_active(
    db: AsyncSession,
    visitor_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = _require_society_id(actor_society_id)
    visitor = await _get_or_404(db, visitor_id, society_id)
    if not active:
        open_visits = await db.execute(
            select(Visit.id).where(
                Visit.visitor_id == visitor.id,
                Visit.society_id == society_id,
                Visit.status.in_(OPEN_VISIT_STATUSES),
            )
        )
        if open_visits.scalar_one_or_none():
            raise ApiError(422, "Cannot deactivate visitor with open visits")

    if active:
        soft_activate(visitor, actor_id)
    else:
        soft_deactivate(visitor, actor_id)
    await db.commit()
    await db.refresh(visitor)
    return {
        "visitor": _visitor_dict(visitor),
        "message": "Visitor activated" if active else "Visitor deactivated",
    }


async def _get_or_404(db: AsyncSession, visitor_id: UUID, society_id: UUID) -> Visitor:
    result = await db.execute(
        select(Visitor).where(Visitor.id == visitor_id, Visitor.society_id == society_id)
    )
    visitor = result.scalar_one_or_none()
    if not visitor:
        raise ApiError(404, "Visitor not found")
    return visitor
