"""Generic SQLAlchemy list query builder — search, filter, sort, paginate."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from Utils.errors import ApiError


class ListQueryBuilder:
    """Composable helper for paginated list endpoints."""

    def __init__(self, model: Type[DeclarativeBase], base: Optional[Select] = None):
        self.model = model
        self.stmt: Select = base if base is not None else select(model)

    def filter_eq(self, column_name: str, value: Any) -> "ListQueryBuilder":
        if value is None:
            return self
        col = getattr(self.model, column_name, None)
        if col is None:
            return self
        self.stmt = self.stmt.where(col == value)
        return self

    def filter_custom(self, clause) -> "ListQueryBuilder":
        if clause is not None:
            self.stmt = self.stmt.where(clause)
        return self

    def search(self, term: Optional[str], *column_names: str) -> "ListQueryBuilder":
        if not term or not term.strip():
            return self
        q = f"%{term.strip()}%"
        clauses = []
        for name in column_names:
            col = getattr(self.model, name, None)
            if col is not None:
                clauses.append(col.ilike(q))
        if clauses:
            self.stmt = self.stmt.where(or_(*clauses))
        return self

    def sort(
        self,
        sort_by: str,
        sort_order: str,
        allowed: Sequence[str],
        default: str = "created_at",
        *,
        secondary: Optional[str] = None,
    ) -> "ListQueryBuilder":
        # Reject unknown sortBy (do not silently fall back)
        if sort_by not in allowed:
            raise ApiError(422, f"sortBy must be one of: {', '.join(allowed)}")
        field = sort_by
        col = getattr(self.model, field, None)
        if col is None:
            raise ApiError(422, f"sortBy must be one of: {', '.join(allowed)}")
        order_fn = asc if sort_order.lower() == "asc" else desc
        order_clauses = [order_fn(col)]
        if secondary and secondary != field:
            sec_col = getattr(self.model, secondary, None)
            if sec_col is not None:
                order_clauses.append(asc(sec_col))
        self.stmt = self.stmt.order_by(*order_clauses)
        return self

    async def paginate(
        self,
        db: AsyncSession,
        *,
        page: int,
        page_size: int,
        serialize: Callable[[Any], Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        count_stmt = select(func.count()).select_from(self.stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        offset = (page - 1) * page_size
        rows = (
            await db.execute(self.stmt.offset(offset).limit(page_size))
        ).scalars().all()
        return [serialize(row) for row in rows], int(total)


def resolve_sort_column(sort_by: str, allowed: Sequence[str], default: str = "created_at") -> str:
    if sort_by not in allowed:
        raise ApiError(422, f"sortBy must be one of: {', '.join(allowed)}")
    return sort_by
