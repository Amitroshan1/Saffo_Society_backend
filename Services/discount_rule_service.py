"""Discount rule CRUD service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.discount_rule import DiscountRule
from Schemas.billing import (
    DiscountRuleCreate,
    DiscountRuleListQueryParams,
    DiscountRuleOut,
    DiscountRuleUpdate,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import require_society_id
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_deactivate


def _dict(row: DiscountRule) -> Dict[str, Any]:
    return DiscountRuleOut.from_orm(row).model_dump(mode="json")


async def _get_or_404(db: AsyncSession, entity_id: UUID, society_id: UUID) -> DiscountRule:
    result = await db.execute(
        select(DiscountRule).where(
            DiscountRule.id == entity_id, DiscountRule.society_id == society_id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Discount rule not found")
    return row


async def create_discount_rule(
    db: AsyncSession,
    body: DiscountRuleCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = DiscountRule(
        society_id=society_id,
        charge_head_id=body.chargeHeadId,
        resident_id=body.residentId,
        occupancy_id=body.occupancyId,
        name=body.name,
        discount_type=body.discountType,
        fixed_amount_minor=body.fixedAmountMinor,
        percentage_bps=body.percentageBps,
        scope=body.scope,
        one_time=body.oneTime,
        max_uses=body.maxUses,
        uses_count=0,
        stackable=body.stackable,
        effective_from=body.effectiveFrom,
        effective_to=body.effectiveTo,
        notes=body.notes,
        metadata_json=body.metadata,
        is_active=True,
        version=1,
    )
    apply_create_audit(row, actor_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"discountRule": _dict(row)}


async def list_discount_rules(
    db: AsyncSession,
    query: DiscountRuleListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(DiscountRule)
        .filter_eq("society_id", society_id)
        .search(query.search, "name")
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("name", "created_at", "is_active"),
            default="created_at",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "discountRules": [_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_discount_rule(
    db: AsyncSession, entity_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    return {"discountRule": _dict(row)}


async def update_discount_rule(
    db: AsyncSession,
    entity_id: UUID,
    body: DiscountRuleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = await _get_or_404(db, entity_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "discountType": "discount_type",
        "fixedAmountMinor": "fixed_amount_minor",
        "percentageBps": "percentage_bps",
        "scope": "scope",
        "oneTime": "one_time",
        "maxUses": "max_uses",
        "stackable": "stackable",
        "chargeHeadId": "charge_head_id",
        "residentId": "resident_id",
        "occupancyId": "occupancy_id",
        "effectiveFrom": "effective_from",
        "effectiveTo": "effective_to",
        "notes": "notes",
        "metadata": "metadata_json",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(row, orm_key, data[api_key])
    apply_update_audit(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {"discountRule": _dict(row)}


async def delete_discount_rule(
    db: AsyncSession,
    entity_id: UUID,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    soft_deactivate(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {"discountRule": _dict(row), "message": "Discount rule deactivated"}
