"""Late fee rule CRUD service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.late_fee_rule import LateFeeRule
from Schemas.billing import (
    LateFeeRuleCreate,
    LateFeeRuleListQueryParams,
    LateFeeRuleOut,
    LateFeeRuleUpdate,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import require_society_id
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_deactivate


def _dict(row: LateFeeRule) -> Dict[str, Any]:
    return LateFeeRuleOut.from_orm(row).model_dump(mode="json")


async def _get_or_404(db: AsyncSession, entity_id: UUID, society_id: UUID) -> LateFeeRule:
    result = await db.execute(
        select(LateFeeRule).where(
            LateFeeRule.id == entity_id, LateFeeRule.society_id == society_id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Late fee rule not found")
    return row


async def create_late_fee_rule(
    db: AsyncSession,
    body: LateFeeRuleCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = LateFeeRule(
        society_id=society_id,
        charge_head_id=body.chargeHeadId,
        billing_cycle_id=body.billingCycleId,
        name=body.name,
        grace_days=body.graceDays,
        fee_type=body.feeType,
        fixed_amount_minor=body.fixedAmountMinor,
        percentage_bps=body.percentageBps,
        daily_amount_minor=body.dailyAmountMinor,
        max_penalty_minor=body.maxPenaltyMinor,
        apply_on=body.applyOn,
        priority=body.priority,
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
    return {"lateFeeRule": _dict(row)}


async def list_late_fee_rules(
    db: AsyncSession,
    query: LateFeeRuleListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(LateFeeRule)
        .filter_eq("society_id", society_id)
        .search(query.search, "name")
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("name", "priority", "created_at", "is_active"),
            default="priority",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "lateFeeRules": [_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_late_fee_rule(
    db: AsyncSession, entity_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    return {"lateFeeRule": _dict(row)}


async def update_late_fee_rule(
    db: AsyncSession,
    entity_id: UUID,
    body: LateFeeRuleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = await _get_or_404(db, entity_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "feeType": "fee_type",
        "graceDays": "grace_days",
        "fixedAmountMinor": "fixed_amount_minor",
        "percentageBps": "percentage_bps",
        "dailyAmountMinor": "daily_amount_minor",
        "maxPenaltyMinor": "max_penalty_minor",
        "applyOn": "apply_on",
        "priority": "priority",
        "chargeHeadId": "charge_head_id",
        "billingCycleId": "billing_cycle_id",
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
    return {"lateFeeRule": _dict(row)}


async def delete_late_fee_rule(
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
    return {"lateFeeRule": _dict(row), "message": "Late fee rule deactivated"}
