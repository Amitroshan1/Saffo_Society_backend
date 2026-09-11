"""Charge head CRUD service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.charge_head import ChargeHead
from Schemas.billing import ChargeHeadCreate, ChargeHeadListQueryParams, ChargeHeadOut, ChargeHeadUpdate
from Schemas.common import build_pagination_meta
from Services.billing_helpers import require_society_id
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


def _dict(row: ChargeHead) -> Dict[str, Any]:
    return ChargeHeadOut.from_orm(row).model_dump(mode="json")


async def _get_or_404(db: AsyncSession, entity_id: UUID, society_id: UUID) -> ChargeHead:
    result = await db.execute(
        select(ChargeHead).where(ChargeHead.id == entity_id, ChargeHead.society_id == society_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Charge head not found")
    return row


async def create_charge_head(
    db: AsyncSession,
    body: ChargeHeadCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = ChargeHead(
        society_id=society_id,
        code=body.code,
        name=body.name,
        category=body.category,
        default_amount_minor=body.defaultAmountMinor,
        is_recurring=body.isRecurring,
        is_taxable=body.isTaxable,
        gl_code=body.glCode,
        display_order=body.displayOrder,
        description=body.description,
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(row, actor_id)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(409, "Charge head code already exists") from exc
    await db.refresh(row)
    return {"chargeHead": _dict(row)}


async def list_charge_heads(
    db: AsyncSession,
    query: ChargeHeadListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(ChargeHead)
        .filter_eq("society_id", society_id)
        .search(query.search, "code", "name", "description")
        .filter_eq("category", query.category)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("code", "name", "category", "display_order", "created_at", "is_active"),
            default="display_order",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "chargeHeads": [_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_charge_head(
    db: AsyncSession, entity_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    return {"chargeHead": _dict(row)}


async def update_charge_head(
    db: AsyncSession,
    entity_id: UUID,
    body: ChargeHeadUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = await _get_or_404(db, entity_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "category": "category",
        "defaultAmountMinor": "default_amount_minor",
        "isRecurring": "is_recurring",
        "isTaxable": "is_taxable",
        "glCode": "gl_code",
        "displayOrder": "display_order",
        "description": "description",
        "notes": "notes",
        "metadata": "metadata_json",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(row, orm_key, data[api_key])
    apply_update_audit(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {"chargeHead": _dict(row)}


async def set_charge_head_active(
    db: AsyncSession,
    entity_id: UUID,
    *,
    active: bool,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    if active:
        soft_activate(row, actor_id)
    else:
        soft_deactivate(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {
        "chargeHead": _dict(row),
        "message": "Charge head activated" if active else "Charge head deactivated",
    }
