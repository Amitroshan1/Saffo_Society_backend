"""JWT authentication + RBAC (society + platform)."""

from dataclasses import dataclass
from typing import Callable, List, Optional
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Constants.constants import PLATFORM_ROLES
from Core.security import verify_access_token
from Database.session import get_db
from Models.user import User
from Utils.errors import ApiError

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: UUID
    role: str
    flat: Optional[UUID]
    society_id: Optional[UUID]
    impersonator_id: Optional[UUID] = None
    impersonation_session_id: Optional[UUID] = None

    @property
    def is_platform(self) -> bool:
        return self.role in PLATFORM_ROLES

    @property
    def is_impersonating(self) -> bool:
        return self.impersonator_id is not None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "Access token missing or malformed")

    try:
        decoded = verify_access_token(credentials.credentials)
    except ValueError as exc:
        message = str(exc).lower()
        if "expired" in message:
            raise ApiError(401, "Token expired") from exc
        raise ApiError(401, "Invalid token") from exc

    user_id = decoded.get("userId")
    if not user_id:
        raise ApiError(401, "Invalid token")

    result = await db.execute(select(User).where(User.id == UUID(str(user_id))))
    user = result.scalar_one_or_none()
    if not user:
        raise ApiError(401, "User not found")
    if not user.is_active:
        raise ApiError(403, "Account is deactivated. Contact admin.")

    # Impersonation: token role/society may override DB (target admin session)
    token_role = decoded.get("role") or user.role
    society_raw = decoded.get("societyId")
    society_id = UUID(str(society_raw)) if society_raw else user.society_id

    impersonator_raw = decoded.get("impersonatorId")
    session_raw = decoded.get("impersonationSessionId")
    impersonator_id = UUID(str(impersonator_raw)) if impersonator_raw else None
    impersonation_session_id = UUID(str(session_raw)) if session_raw else None

    if impersonator_id and user.role in PLATFORM_ROLES:
        raise ApiError(403, "Nested impersonation is not allowed")

    return CurrentUser(
        user_id=user.id,
        role=token_role if impersonator_id else user.role,
        flat=user.flat_id,
        society_id=society_id,
        impersonator_id=impersonator_id,
        impersonation_session_id=impersonation_session_id,
    )


def require_roles(*roles: str) -> Callable:
    allowed: List[str] = list(roles)

    async def _checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in allowed:
            raise ApiError(
                403,
                f"Access denied. Required roles: {', '.join(allowed)}",
            )
        return current

    return _checker
