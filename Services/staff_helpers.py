"""Shared staff/gate/shift helpers and constants."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Models.building import Building
from Models.gate import Gate
from Models.resident import Resident
from Models.shift import Shift
from Models.staff import Staff
from Models.user import User
from Schemas.gate import GATE_TYPE_VALUES
from Schemas.shift import (
    ATTENDANCE_STATUS_VALUES,
    SHIFT_STATUS_VALUES,
    SHIFT_TYPE_VALUES,
)
from Schemas.staff import EMPLOYMENT_TYPE_VALUES, STAFF_ROLE_VALUES
from Utils.audit import apply_create_audit, apply_update_audit
from Utils.errors import ApiError

TERMINAL_SHIFT_STATUSES = frozenset({"completed", "cancelled", "no_show"})

__all__ = [
    "STAFF_ROLE_VALUES",
    "EMPLOYMENT_TYPE_VALUES",
    "GATE_TYPE_VALUES",
    "SHIFT_TYPE_VALUES",
    "SHIFT_STATUS_VALUES",
    "ATTENDANCE_STATUS_VALUES",
    "TERMINAL_SHIFT_STATUSES",
    "utcnow",
    "next_staff_code",
    "get_staff_in_society",
    "get_gate_in_society",
    "get_shift_in_society",
    "get_building_in_society",
    "ensure_user_linkable_for_staff",
    "get_staff_for_user",
    "ensure_staff_profile_for_user",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def next_staff_code(db: AsyncSession, society_id: UUID) -> str:
    result = await db.execute(
        select(Staff.code)
        .where(Staff.society_id == society_id, Staff.code.like("STF-%"))
        .order_by(Staff.code.desc())
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
    return f"STF-{num:06d}"


async def get_staff_in_society(db: AsyncSession, staff_id: UUID, society_id: UUID) -> Staff:
    result = await db.execute(
        select(Staff).where(Staff.id == staff_id, Staff.society_id == society_id)
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise ApiError(404, "Staff not found")
    return staff


async def get_gate_in_society(db: AsyncSession, gate_id: UUID, society_id: UUID) -> Gate:
    result = await db.execute(
        select(Gate).where(Gate.id == gate_id, Gate.society_id == society_id)
    )
    gate = result.scalar_one_or_none()
    if not gate:
        raise ApiError(404, "Gate not found")
    return gate


async def get_shift_in_society(db: AsyncSession, shift_id: UUID, society_id: UUID) -> Shift:
    result = await db.execute(
        select(Shift).where(Shift.id == shift_id, Shift.society_id == society_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise ApiError(404, "Shift not found")
    return shift


async def get_building_in_society(
    db: AsyncSession, building_id: UUID, society_id: UUID
) -> Building:
    result = await db.execute(
        select(Building).where(Building.id == building_id, Building.society_id == society_id)
    )
    building = result.scalar_one_or_none()
    if not building:
        raise ApiError(404, "Building not found")
    return building


async def ensure_user_linkable_for_staff(
    db: AsyncSession,
    user_id: UUID,
    society_id: UUID,
    *,
    except_staff_id: UUID | None = None,
) -> User:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found")
    if user.society_id != society_id:
        raise ApiError(422, "User must belong to the same society")

    resident = await db.execute(
        select(Resident).where(Resident.user_id == user_id, Resident.is_active.is_(True))
    )
    if resident.scalar_one_or_none():
        raise ApiError(409, "User is already linked to a resident")

    query = select(Staff).where(Staff.user_id == user_id, Staff.is_active.is_(True))
    if except_staff_id:
        query = query.where(Staff.id != except_staff_id)
    existing = await db.execute(query)
    if existing.scalar_one_or_none():
        raise ApiError(409, "User is already linked to another staff member")
    return user


async def _staff_for_user_id(
    db: AsyncSession, user_id: UUID, society_id: UUID
) -> Staff | None:
    result = await db.execute(
        select(Staff)
        .where(Staff.user_id == user_id, Staff.society_id == society_id)
        .order_by(Staff.is_active.desc(), Staff.created_at.asc())
        .limit(1)
    )
    return result.scalars().first()


async def _default_gate_id(db: AsyncSession, society_id: UUID) -> UUID | None:
    result = await db.execute(
        select(Gate)
        .where(Gate.society_id == society_id, Gate.is_active.is_(True))
        .order_by(Gate.sequence.asc(), Gate.created_at.asc())
        .limit(1)
    )
    gate = result.scalars().first()
    return gate.id if gate else None


async def _link_unmatched_staff_for_guard(
    db: AsyncSession, user: User, society_id: UUID
) -> Staff | None:
    match_parts = []
    if user.phone:
        match_parts.append(Staff.phone == user.phone)
    if user.email:
        match_parts.append(func.lower(Staff.email) == user.email.lower())
    if not match_parts:
        return None

    result = await db.execute(
        select(Staff)
        .where(
            Staff.society_id == society_id,
            Staff.user_id.is_(None),
            Staff.is_active.is_(True),
            or_(*match_parts),
        )
        .order_by(Staff.created_at.asc())
        .limit(1)
    )
    staff = result.scalars().first()
    if not staff:
        return None
    staff.user_id = user.id
    if not staff.name and user.name:
        staff.name = user.name
    if not staff.email and user.email:
        staff.email = user.email
    apply_update_audit(staff, user.id)
    await db.flush()
    return staff


async def _create_guard_staff(db: AsyncSession, user: User, society_id: UUID) -> Staff:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            async with db.begin_nested():
                code = await next_staff_code(db, society_id)
                if attempt:
                    try:
                        num = int(code.split("-", 1)[1]) + attempt
                    except (IndexError, ValueError):
                        num = attempt + 1
                    code = f"STF-{num:06d}"
                staff = Staff(
                    society_id=society_id,
                    user_id=user.id,
                    code=code,
                    name=user.name,
                    phone=user.phone,
                    email=user.email,
                    staff_role="security_guard",
                    department="security",
                    employment_type="permanent",
                    assigned_gate_id=await _default_gate_id(db, society_id),
                    joining_date=date.today(),
                    metadata_json={},
                    is_active=True,
                    version=1,
                )
                apply_create_audit(staff, user.id)
                db.add(staff)
                await db.flush()
                return staff
        except IntegrityError as exc:
            last_error = exc
    raise ApiError(409, "Could not create staff profile for this account") from last_error


async def ensure_staff_profile_for_user(
    db: AsyncSession, user_id: UUID, society_id: UUID
) -> Staff:
    """Return the staff row for a user, linking or creating one for guards."""
    staff = await _staff_for_user_id(db, user_id, society_id)
    if staff:
        if not staff.is_active:
            raise ApiError(422, "Staff profile is inactive")
        return staff

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ApiError(404, "User not found")
    if user.society_id != society_id:
        raise ApiError(422, "User must belong to the same society")
    if user.role != "guard":
        raise ApiError(422, "Staff profile not linked to your account")

    linked = await _link_unmatched_staff_for_guard(db, user, society_id)
    if linked:
        return linked
    return await _create_guard_staff(db, user, society_id)


async def get_staff_for_user(db: AsyncSession, user_id: UUID, society_id: UUID) -> Staff:
    return await ensure_staff_profile_for_user(db, user_id, society_id)
