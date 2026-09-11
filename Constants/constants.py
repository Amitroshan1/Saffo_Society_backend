"""Shared constants and role definitions for RBAC."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    FINANCE = "finance"
    RESIDENT = "resident"
    GUARD = "guard"
    # Phase 17 — platform control plane (society_id IS NULL)
    SUPER_ADMIN = "super_admin"
    PLATFORM_SUPPORT = "platform_support"
    PLATFORM_AUDITOR = "platform_auditor"
    PLATFORM_BILLING = "platform_billing"  # future-ready


SOCIETY_ROLES = (
    UserRole.ADMIN.value,
    UserRole.FINANCE.value,
    UserRole.RESIDENT.value,
    UserRole.GUARD.value,
)

PLATFORM_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.PLATFORM_SUPPORT.value,
    UserRole.PLATFORM_AUDITOR.value,
    UserRole.PLATFORM_BILLING.value,
)

PANEL_ROLES = [r.value for r in UserRole]

# Public registration / society panels only
SOCIETY_PANEL_ROLES = list(SOCIETY_ROLES)

GENDER_VALUES = ("Male", "Female", "Other", "Prefer not to say")
BLOOD_GROUP_VALUES = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_#^()\-+=]).{8,}$"
PHONE_REGEX = r"^[6-9]\d{9}$"

MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
OTP_EXPIRY_MINUTES = 10
