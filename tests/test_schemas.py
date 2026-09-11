"""Smoke tests for schema validation (no DB required)."""

import pytest
from pydantic import ValidationError

from Schemas.auth import LoginRequest, RegisterRequest


def test_login_requires_role():
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com", password="Secret1!")


def test_register_password_strength():
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Test User",
            email="test@example.com",
            phone="9876543210",
            password="weak",
            role="resident",
        )


def test_register_ok():
    body = RegisterRequest(
        name="Test User",
        email="test@example.com",
        phone="9876543210",
        password="Secret1!x",
        role="resident",
    )
    assert body.role.value == "resident"
