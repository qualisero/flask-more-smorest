"""Unit tests for the CRUD pagination mixin."""

import json
from typing import cast

import pytest
from flask_smorest.pagination import PaginationMixin, PaginationParameters
from werkzeug.exceptions import BadRequest

from flask_more_smorest.crud.pagination import CRUDPaginationMixin


class DummyPagination(CRUDPaginationMixin):
    """Simple helper to exercise pagination logic without a full blueprint."""

    PAGINATION_HEADER_NAME = None


class DummyPaginationWithHeaders(CRUDPaginationMixin, PaginationMixin):
    """Helper with headers enabled to validate metadata behavior."""

    PAGINATION_HEADER_NAME = "X-Pagination"


def test_paginate_rejects_non_positive_page() -> None:
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={"page": 0, "page_size": 5})


def test_paginate_page_size_zero_is_valid() -> None:
    """page_size=0 means 'return all' and should not raise."""
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    result = handler(filters={"page": 1, "page_size": 0})
    # Should not raise - page_size=0 is valid
    assert result is not None


def test_paginate_page_size_zero_sets_zero() -> None:
    """When page_size=0, pagination_parameters.page_size should be 0."""
    dummy = DummyPagination()
    captured: dict[str, object] = {}

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        captured["pp"] = kwargs["pagination_parameters"]
        return []

    handler(filters={"page": 1, "page_size": 0})
    assert cast(PaginationParameters, captured["pp"]).page_size == 0


def test_paginate_rejects_negative_page_size() -> None:
    """page_size=-1 should still be rejected."""
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={"page": 1, "page_size": -1})


def test_paginate_default_page_size_is_20() -> None:
    """Default page_size should be 20 when not specified."""
    dummy = DummyPagination()
    captured: dict[str, object] = {}

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        captured["pp"] = kwargs["pagination_parameters"]
        return []

    handler(filters={"page": 1})
    assert cast(PaginationParameters, captured["pp"]).page_size == 20


def test_paginate_rejects_invalid_types() -> None:
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={"page": "abc", "page_size": 5})


def test_paginate_raises_for_invalid_default() -> None:
    dummy = DummyPagination()

    @dummy.paginate(page=0)
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={})


def test_paginate_page_size_zero_includes_safe_header_metadata() -> None:
    dummy = DummyPaginationWithHeaders()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[int]:  # pragma: no cover - exercised via wrapper
        pagination_parameters = cast(PaginationParameters, kwargs["pagination_parameters"])
        pagination_parameters.item_count = 5
        return [1, 2, 3, 4, 5]

    result, status, headers = handler(filters={"page": 1, "page_size": 0})

    assert status == 200
    assert result == [1, 2, 3, 4, 5]
    assert "X-Pagination" in headers
    metadata = json.loads(headers["X-Pagination"])
    assert metadata["total"] == 5
    assert metadata["total_pages"] == 1


def test_paginate_page_size_zero_empty_result() -> None:
    """page_size=0 with empty results should not error."""
    dummy = DummyPagination()
    dummy.PAGINATION_HEADER_NAME = "X-Pagination"  # type: ignore[assignment]

    def fake_set_pagination_metadata(params: object, result: object, headers: object) -> tuple[object, object]:
        assert isinstance(headers, dict)
        assert isinstance(params, PaginationParameters)
        headers["X-Pagination"] = f'{{"total": {params.item_count}, "total_pages": 1}}'
        return result, headers

    dummy._set_pagination_metadata = fake_set_pagination_metadata  # type: ignore[attr-defined]

    captured: dict[str, PaginationParameters] = {}

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:
        pp = cast(PaginationParameters, kwargs["pagination_parameters"])
        pp.item_count = 0
        captured["pp"] = pp
        return []

    result = handler(filters={"page": 1, "page_size": 0})
    assert captured["pp"].page_size == 0
    assert result is not None
