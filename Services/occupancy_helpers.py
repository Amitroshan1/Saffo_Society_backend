"""Shared occupancy helpers — flat derivation, user sync, resident codes."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.user import User
from Models.wing import Wing
from Utils.errors import ApiError


OCCUPANCY_ROLE_VALUES = ("owner", "tenant", "family_member", "domestic_help")
OCCUPANCY_STATUS_VALUES = ("active", "ended", "cancelled")
ENDED_REASON_VALUES = ("moved_out", "lease_ended", "transfer", "deceased", "other")

FACILITY_STATUSES = frozenset({"blocked", "under_maintenance"})


async def next_resident_code(db: AsyncSession, society_id: UUID) -> str:
    result = await db.execute(
        select(Resident.code)
        .where(Resident.society_id == society_id, Resident.code.like("RES-%"))
        .order_by(Resident.code.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last:
        try:
            num = int(last.split("-", 1)[1]) + 1
        except (IndexError, ValueError):
            num = 1
    else:
        num = 1
    return f"RES-{num:06d}"


async def get_flat_in_society(
    db: AsyncSession, flat_id: UUID, society_id: UUID, *, require_active: bool = False
) -> Flat:
    result = await db.execute(
        select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id)
    )
    flat = result.scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")
    if require_active and not flat.is_active:
        raise ApiError(422, "Flat is inactive")
    return flat


async def get_resident_in_society(
    db: AsyncSession, resident_id: UUID, society_id: UUID
) -> Resident:
    result = await db.execute(
        select(Resident).where(Resident.id == resident_id, Resident.society_id == society_id)
    )
    resident = result.scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")
    return resident


async def count_active_occupancies(db: AsyncSession, flat_id: UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Occupancy)
        .where(Occupancy.flat_id == flat_id, Occupancy.status == "active")
    )
    return int(result.scalar_one())


async def derive_flat_from_occupancies(db: AsyncSession, flat: Flat) -> None:
    if flat.status in FACILITY_STATUSES:
        return

    active = await db.execute(
        select(Occupancy).where(
            Occupancy.flat_id == flat.id,
            Occupancy.status == "active",
        )
    )
    rows = list(active.scalars().all())
    if not rows:
        flat.status = "vacant"
        if flat.ownership_type != "company_leased":
            flat.ownership_type = "vacant"
        return

    flat.status = "occupied"
    roles = {r.role for r in rows}
    if "tenant" in roles:
        flat.ownership_type = "rented"
    elif "owner" in roles:
        flat.ownership_type = "owned"


async def sync_user_flat_for_resident(
    db: AsyncSession, resident: Resident, *, preferred_flat_id: Optional[UUID] = None
) -> None:
    if not resident.user_id:
        return

    user_result = await db.execute(select(User).where(User.id == resident.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return

    flat_id = preferred_flat_id
    if not flat_id:
        occ_result = await db.execute(
            select(Occupancy)
            .where(
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
            )
            .order_by(Occupancy.is_primary.desc(), Occupancy.move_in_date.desc())
            .limit(1)
        )
        occ = occ_result.scalar_one_or_none()
        flat_id = occ.flat_id if occ else None

    if flat_id:
        flat = await get_flat_in_society(db, flat_id, resident.society_id)
        wing = (
            await db.execute(select(Wing).where(Wing.id == flat.wing_id))
        ).scalar_one_or_none()
        building = (
            await db.execute(select(Building).where(Building.id == flat.building_id))
        ).scalar_one_or_none()
        user.flat_id = flat.id
        user.flat_no = flat.flat_no
        user.wing = wing.code if wing else None
        user.building = building.name if building else None
    else:
        user.flat_id = None


async def clear_user_flat_if_no_active_occupancy(
    db: AsyncSession, user_id: UUID, society_id: UUID
) -> None:
    resident_result = await db.execute(
        select(Resident).where(Resident.user_id == user_id, Resident.society_id == society_id)
    )
    resident = resident_result.scalar_one_or_none()
    if not resident:
        return

    active = await db.execute(
        select(func.count())
        .select_from(Occupancy)
        .where(Occupancy.resident_id == resident.id, Occupancy.status == "active")
    )
    if int(active.scalar_one()) == 0:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.flat_id = None


async def demote_other_primaries(
    db: AsyncSession, flat_id: UUID, *, except_id: Optional[UUID] = None
) -> None:
    query = select(Occupancy).where(
        Occupancy.flat_id == flat_id,
        Occupancy.status == "active",
        Occupancy.is_primary.is_(True),
    )
    if except_id:
        query = query.where(Occupancy.id != except_id)
    result = await db.execute(query)
    for occ in result.scalars().all():
        occ.is_primary = False


async def ensure_user_linkable(
    db: AsyncSession, user_id: UUID, society_id: UUID, *, except_resident_id: Optional[UUID] = None
) -> User:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found")
    if user.society_id != society_id:
        raise ApiError(422, "User must belong to the same society")

    query = select(Resident).where(Resident.user_id == user_id, Resident.is_active.is_(True))
    if except_resident_id:
        query = query.where(Resident.id != except_resident_id)
    existing = await db.execute(query)
    if existing.scalar_one_or_none():
        raise ApiError(409, "User is already linked to another resident")
    return user


def validate_move_out_dates(move_in: date, move_out: date) -> None:
    if move_out < move_in:
        raise ApiError(422, "moveOutDate must be on or after moveInDate")
