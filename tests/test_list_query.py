"""Tests for list query utilities."""

import pytest

from Schemas.common import ListQueryParams, build_pagination_meta


def test_build_pagination_meta_first_page():
    meta = build_pagination_meta(1, 10, 25)
    assert meta["page"] == 1
    assert meta["pageSize"] == 10
    assert meta["total"] == 25
    assert meta["totalPages"] == 3
    assert meta["hasNext"] is True
    assert meta["hasPrev"] is False


def test_build_pagination_meta_empty():
    meta = build_pagination_meta(1, 20, 0)
    assert meta["total"] == 0
    assert meta["totalPages"] == 1
    assert meta["hasNext"] is False


def test_list_query_params_aliases():
    q = ListQueryParams(pageSize=5, sortBy="name", sortOrder="asc", isActive=True)
    assert q.page_size == 5
    assert q.sort_by == "name"
    assert q.is_active is True
