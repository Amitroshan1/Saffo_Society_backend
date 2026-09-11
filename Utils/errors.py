"""Operational API error — replaces server/utils/ApiError.js."""

from typing import Any, List, Optional


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        errors: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        self.is_operational = True
