"""Response helpers matching Node ApiResponse shape."""

from typing import Any, Dict, List, Optional

from fastapi.responses import JSONResponse

from Schemas.common import build_pagination_meta


def success_response(
    status_code: int = 200,
    message: str = "Success",
    data: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data or {},
        },
    )


def paginated_response(
    *,
    items: List[Any],
    page: int,
    page_size: int,
    total: int,
    items_key: str = "items",
    message: str = "Success",
    status_code: int = 200,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    payload: Dict[str, Any] = {
        items_key: items,
        "pagination": build_pagination_meta(page, page_size, total),
    }
    if extra:
        payload.update(extra)
    return success_response(status_code, message, payload)


def error_body(
    message: str,
    errors: Optional[list] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "errors": errors or [],
    }
