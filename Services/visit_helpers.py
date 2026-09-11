"""Shared visitor/visit helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.visitor import Visitor
from Models.visit import Visit
from Utils.errors import ApiError

VISITOR_TYPE_VALUES = (
    "guest",
    "delivery",
    "maid",
    "driver",
    "technician",
    "vendor",
    "courier",
    "other",
)

VISIT_STATUS_VALUES = (
    "scheduled",
    "waiting",
    "approved",
    "rejected",
    "checked_in",
    "checked_out",
    "cancelled",
    "expired",
)

PASS_TYPE_VALUES = ("one_time", "daily", "temporary", "service", "delivery")

TERMINAL_VISIT_STATUSES = frozenset({"checked_out", "cancelled", "rejected", "expired"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_visitor_in_society(db: AsyncSession, visitor_id: UUID, society_id: UUID) -> Visitor:
    result = await db.execute(
        select(Visitor).where(Visitor.id == visitor_id, Visitor.society_id == society_id)
    )
    visitor = result.scalar_one_or_none()
    if not visitor:
        raise ApiError(404, "Visitor not found")
    return visitor


async def get_occupancy_in_society(db: AsyncSession, occupancy_id: UUID, society_id: UUID) -> Occupancy:
    result = await db.execute(
        select(Occupancy).where(Occupancy.id == occupancy_id, Occupancy.society_id == society_id)
    )
    occupancy = result.scalar_one_or_none()
    if not occupancy:
        raise ApiError(404, "Occupancy not found")
    return occupancy


async def get_visit_in_society(db: AsyncSession, visit_id: UUID, society_id: UUID) -> Visit:
    result = await db.execute(select(Visit).where(Visit.id == visit_id, Visit.society_id == society_id))
    visit = result.scalar_one_or_none()
    if not visit:
        raise ApiError(404, "Visit not found")
    return visit


async def get_flat_in_society(db: AsyncSession, flat_id: UUID, society_id: UUID) -> Flat:
    result = await db.execute(select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id))
    flat = result.scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")
    return flat


def assert_check_out_not_before_check_in(check_in: datetime | None, check_out: datetime | None) -> None:
    if check_in and check_out and check_out < check_in:
        raise ApiError(422, "checkOutTime must be on or after checkInTime")


def assert_not_terminal(status: str) -> None:
    if status in TERMINAL_VISIT_STATUSES:
        raise ApiError(422, f"Visit is {status} and read-only")
