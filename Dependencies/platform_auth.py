"""Platform RBAC dependencies."""

from typing import Callable, List

from fastapi import Depends

from Constants.constants import PLATFORM_ROLES, UserRole
from Dependencies.auth import CurrentUser, get_current_user
from Utils.errors import ApiError


def require_platform_roles(*roles: str) -> Callable:
    allowed: List[str] = list(roles) if roles else list(PLATFORM_ROLES)

    async def _checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in allowed:
            raise ApiError(
                403,
                f"Platform access denied. Required roles: {', '.join(allowed)}",
            )
        if current.society_id is not None and not current.is_impersonating:
            # Platform operators must not carry a society unless impersonating
            if current.role in PLATFORM_ROLES:
                pass  # society_id should be null for platform users; tolerate leftover
        if current.is_impersonating:
            raise ApiError(403, "End impersonation before using platform APIs")
        return current

    return _checker


require_super_admin = require_platform_roles(UserRole.SUPER_ADMIN.value)

require_platform_write = require_platform_roles(
    UserRole.SUPER_ADMIN.value,
    UserRole.PLATFORM_SUPPORT.value,
    UserRole.PLATFORM_BILLING.value,
)

require_platform_read = require_platform_roles(
    UserRole.SUPER_ADMIN.value,
    UserRole.PLATFORM_SUPPORT.value,
    UserRole.PLATFORM_AUDITOR.value,
    UserRole.PLATFORM_BILLING.value,
)

require_impersonate = require_platform_roles(
    UserRole.SUPER_ADMIN.value,
    UserRole.PLATFORM_SUPPORT.value,
)
