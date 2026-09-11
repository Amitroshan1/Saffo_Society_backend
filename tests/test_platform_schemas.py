"""Phase 17 platform schema / helper tests (no DB)."""

import pytest
from pydantic import ValidationError

from Constants.constants import PLATFORM_ROLES, SOCIETY_ROLES, UserRole
from Schemas.auth import LoginRequest, RegisterRequest
from Schemas.platform import ImpersonateRequest, TenantCreate
from Services.platform_helpers import DEFAULT_FEATURE_FLAGS, DEFAULT_PLANS, generate_license_key


def test_platform_roles_defined():
    assert UserRole.SUPER_ADMIN.value in PLATFORM_ROLES
    assert "admin" in SOCIETY_ROLES
    assert UserRole.SUPER_ADMIN.value not in SOCIETY_ROLES


def test_register_rejects_platform_role():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="X",
            email="x@example.com",
            phone="9876543210",
            password="Admin@123",
            role=UserRole.SUPER_ADMIN,
        )


def test_login_allows_super_admin_role():
    body = LoginRequest(
        email="superadmin@platform.com",
        password="Admin@123",
        role=UserRole.SUPER_ADMIN,
    )
    assert body.role == UserRole.SUPER_ADMIN


def test_tenant_create_schema():
    body = TenantCreate(
        name="Green Heights",
        code="GREEN-01",
        adminEmail="admin@green.com",
        planCode="trial",
    )
    assert body.code == "GREEN-01"


def test_impersonate_reason_min_length():
    with pytest.raises(ValidationError):
        ImpersonateRequest(reason="no")


def test_default_catalogs():
    assert len(DEFAULT_FEATURE_FLAGS) >= 6
    assert any(p["code"] == "enterprise" for p in DEFAULT_PLANS)
    key = generate_license_key()
    assert key.startswith("LIC-")
    assert len(key) > 10
