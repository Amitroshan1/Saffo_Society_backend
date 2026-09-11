"""Reusable validation helpers."""

from __future__ import annotations

import re
from typing import Optional

from Utils.errors import ApiError

PINCODE_IN_REGEX = re.compile(r"^\d{6}$")


def require_non_blank(value: Optional[str], field: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ApiError(422, f"{field} cannot be blank")
    return v


def validate_india_pincode(country: str, pincode: str) -> None:
    if (country or "IN").upper() == "IN" and not PINCODE_IN_REGEX.fullmatch(pincode):
        raise ApiError(422, "pincode must be 6 digits for India")


def normalize_code(code: str) -> str:
    return code.strip().upper()
