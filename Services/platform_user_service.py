"""Platform user management (super_admin / support / auditor / billing)."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import PLATFORM_ROLES, SOCIETY_ROLES
from Core.security import hash_password
from Models.user import User
from Services.platform_helpers import generate_temp_password, iso, write_audit
from Utils.errors import ApiError


def platform_user_to_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "name": u.name,
        "email": u.email,
        "phone": u.phone,
        "role": u.role,
        "isActive": u.is_active,
        "isVerified": u.is_verified,
        "societyId": str(u.society_id) if u.society_id else None,
        "createdAt": iso(u.created_at),
    }


async def list_platform_users(db: AsyncSession) -> List[dict]:
    rows = (
        await db.execute(
            select(User)
            .where(User.role.in_(list(PLATFORM_ROLES)))
            .order_by(User.created_at.desc())
        )
    ).scalars().all()
    return [platform_user_to_dict(u) for u in rows]


async def create_platform_user(
    db: AsyncSession,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    if actor_role != "super_admin":
        raise ApiError(403, "Only super_admin can create platform users")
    role = body.get("role") or "platform_support"
    if role not in PLATFORM_ROLES:
        raise ApiError(422, f"Invalid platform role: {role}")
    email = str(body["email"]).lower().strip()
    phone = str(body["phone"]).strip()
    existing = await db.execute(
        select(User).where((User.email == email) | (User.phone == phone))
    )
    if existing.scalar_one_or_none():
        raise ApiError(409, "Email or phone already registered")
    password = body.get("password") or generate_temp_password()
    user = User(
        name=body["name"].strip(),
        email=email,
        phone=phone,
        password=hash_password(password),
        role=role,
        society_id=None,
        is_active=True,
        is_verified=True,
        designation=body.get("designation") or role,
    )
    db.add(user)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="platform_user.create",
        resource_type="user",
        resource_id=str(user.id),
        after=platform_user_to_dict(user),
    )
    await db.commit()
    await db.refresh(user)
    data = platform_user_to_dict(user)
    if not body.get("password"):
        data["tempPassword"] = password
    return data


async def update_platform_user(
    db: AsyncSession,
    user_id: UUID,
    body: Dict[str, Any],
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    if actor_role != "super_admin":
        raise ApiError(403, "Only super_admin can update platform users")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role not in PLATFORM_ROLES:
        raise ApiError(404, "Platform user not found")
    if "name" in body and body["name"]:
        user.name = body["name"].strip()
    if "role" in body and body["role"]:
        if body["role"] not in PLATFORM_ROLES:
            raise ApiError(422, "Invalid platform role")
        user.role = body["role"]
    if "isActive" in body and body["isActive"] is not None:
        user.is_active = bool(body["isActive"])
    await write_audit(
        db,
        actor_user_id=actor_id,
        actor_role=actor_role,
        action="platform_user.update",
        resource_type="user",
        resource_id=str(user.id),
        after=platform_user_to_dict(user),
    )
    await db.commit()
    await db.refresh(user)
    return platform_user_to_dict(user)


def global_roles_catalog() -> List[dict]:
    return [
        {
            "role": "super_admin",
            "plane": "platform",
            "description": "Full platform control",
            "permissions": ["*"],
        },
        {
            "role": "platform_support",
            "plane": "platform",
            "description": "Tenant lifecycle + impersonation",
            "permissions": ["tenants.*", "impersonate", "announcements"],
        },
        {
            "role": "platform_auditor",
            "plane": "platform",
            "description": "Read-only dashboards and audit",
            "permissions": ["read"],
        },
        {
            "role": "platform_billing",
            "plane": "platform",
            "description": "Subscriptions and licenses (future-ready)",
            "permissions": ["subscriptions.*", "licenses.*"],
        },
        *[
            {
                "role": r,
                "plane": "society",
                "description": f"Society {r} (locked Phase 1)",
                "permissions": ["society_scoped"],
            }
            for r in SOCIETY_ROLES
        ],
    ]
