"""Billing cycle CRUD service."""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.billing_cycle import BillingCycle
from Schemas.billing import (
    BillingCycleCreate,
    BillingCycleListQueryParams,
    BillingCycleOut,
    BillingCycleUpdate,
)
from Schemas.common import build_pagination_meta
from Services.billing_helpers import require_society_id
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError
from Utils.query import ListQueryBuilder
from Utils.soft_delete import soft_activate, soft_deactivate


def _dict(row: BillingCycle) -> Dict[str, Any]:
    return BillingCycleOut.from_orm(row).model_dump(mode="json")


async def _get_or_404(db: AsyncSession, entity_id: UUID, society_id: UUID) -> BillingCycle:
    result = await db.execute(
        select(BillingCycle).where(
            BillingCycle.id == entity_id, BillingCycle.society_id == society_id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise ApiError(404, "Billing cycle not found")
    return row


async def create_billing_cycle(
    db: AsyncSession,
    body: BillingCycleCreate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = BillingCycle(
        society_id=society_id,
        code=body.code,
        name=body.name,
        frequency=body.frequency,
        day_of_month=body.dayOfMonth,
        custom_cron=body.customCron,
        period_label_template=body.periodLabelTemplate,
        default_due_days=body.defaultDueDays,
        auto_publish=body.autoPublish,
        next_run_at=body.nextRunAt,
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
        raise ApiError(409, "Billing cycle code already exists") from exc
    await db.refresh(row)
    return {"billingCycle": _dict(row)}


async def list_billing_cycles(
    db: AsyncSession,
    query: BillingCycleListQueryParams,
    *,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    builder = (
        ListQueryBuilder(BillingCycle)
        .filter_eq("society_id", society_id)
        .search(query.search, "code", "name")
        .filter_eq("frequency", query.frequency)
        .filter_eq("is_active", query.is_active)
        .sort(
            query.sort_by,
            query.sort_order,
            ("code", "name", "frequency", "created_at", "is_active", "next_run_at"),
            default="created_at",
        )
    )
    items, total = await builder.paginate(
        db, page=query.page, page_size=query.page_size, serialize=lambda x: x
    )
    return {
        "billingCycles": [_dict(x) for x in items],
        "pagination": build_pagination_meta(query.page, query.page_size, total),
    }


async def get_billing_cycle(
    db: AsyncSession, entity_id: UUID, *, actor_society_id: UUID | None
) -> Dict[str, Any]:
    row = await _get_or_404(db, entity_id, require_society_id(actor_society_id))
    return {"billingCycle": _dict(row)}


async def update_billing_cycle(
    db: AsyncSession,
    entity_id: UUID,
    body: BillingCycleUpdate,
    *,
    actor_id: UUID,
    actor_society_id: UUID | None,
) -> Dict[str, Any]:
    society_id = require_society_id(actor_society_id)
    row = await _get_or_404(db, entity_id, society_id)
    data = body.model_dump(exclude_unset=True)
    field_map = {
        "name": "name",
        "frequency": "frequency",
        "dayOfMonth": "day_of_month",
        "customCron": "custom_cron",
        "periodLabelTemplate": "period_label_template",
        "defaultDueDays": "default_due_days",
        "autoPublish": "auto_publish",
        "nextRunAt": "next_run_at",
        "notes": "notes",
        "metadata": "metadata_json",
    }
    for api_key, orm_key in field_map.items():
        if api_key in data:
            setattr(row, orm_key, data[api_key])
    apply_update_audit(row, actor_id)
    await db.commit()
    await db.refresh(row)
    return {"billingCycle": _dict(row)}


async def set_billing_cycle_active(
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
        "billingCycle": _dict(row),
        "message": "Billing cycle activated" if active else "Billing cycle deactivated",
    }
