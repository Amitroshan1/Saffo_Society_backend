"""Complaint helpers — ownership and related entity lookups."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.complaint import Complaint
from Models.flat import Flat
from Models.occupancy import Occupancy
from Models.resident import Resident
from Models.staff import Staff
from Utils.errors import ApiError


async def get_complaint_in_society(
    db: AsyncSession, complaint_id: UUID, society_id: UUID
) -> Complaint:
    result = await db.execute(
        select(Complaint).where(
            Complaint.id == complaint_id,
            Complaint.society_id == society_id,
        )
    )
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise ApiError(404, "Complaint not found")
    return complaint


async def get_occupancy_in_society(
    db: AsyncSession, occupancy_id: UUID, society_id: UUID
) -> Occupancy:
    result = await db.execute(
        select(Occupancy).where(
            Occupancy.id == occupancy_id,
            Occupancy.society_id == society_id,
        )
    )
    occupancy = result.scalar_one_or_none()
    if not occupancy:
        raise ApiError(404, "Occupancy not found")
    return occupancy


async def get_resident_in_society(
    db: AsyncSession, resident_id: UUID, society_id: UUID
) -> Resident:
    result = await db.execute(
        select(Resident).where(
            Resident.id == resident_id,
            Resident.society_id == society_id,
        )
    )
    resident = result.scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident not found")
    return resident


async def get_flat_in_society(db: AsyncSession, flat_id: UUID, society_id: UUID) -> Flat:
    result = await db.execute(
        select(Flat).where(Flat.id == flat_id, Flat.society_id == society_id)
    )
    flat = result.scalar_one_or_none()
    if not flat:
        raise ApiError(404, "Flat not found")
    return flat


async def get_staff_in_society(db: AsyncSession, staff_id: UUID, society_id: UUID) -> Staff:
    result = await db.execute(
        select(Staff).where(Staff.id == staff_id, Staff.society_id == society_id)
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise ApiError(404, "Staff not found")
    return staff


async def get_staff_for_user(
    db: AsyncSession, user_id: UUID, society_id: UUID
) -> Staff | None:
    result = await db.execute(
        select(Staff).where(
            Staff.user_id == user_id,
            Staff.society_id == society_id,
            Staff.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def resolve_resident_context(
    db: AsyncSession, *, actor_id: UUID, society_id: UUID
) -> tuple[Resident, Occupancy]:
    resident = (
        await db.execute(
            select(Resident).where(
                Resident.society_id == society_id,
                Resident.user_id == actor_id,
                Resident.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not resident:
        raise ApiError(404, "Resident profile not found")

    occupancy = (
        await db.execute(
            select(Occupancy)
            .where(
                Occupancy.society_id == society_id,
                Occupancy.resident_id == resident.id,
                Occupancy.status == "active",
                Occupancy.is_active.is_(True),
            )
            .order_by(Occupancy.is_primary.desc(), Occupancy.move_in_date.desc())
        )
    ).scalars().first()
    if not occupancy:
        raise ApiError(404, "Active occupancy not found for resident")
    return resident, occupancy
