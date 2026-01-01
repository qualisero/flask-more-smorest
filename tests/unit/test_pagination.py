"""Unit tests for the CRUD pagination mixin."""

import pytest
from werkzeug.exceptions import BadRequest

from flask_more_smorest.pagination import CRUDPaginationMixin


class DummyPagination(CRUDPaginationMixin):
    """Simple helper to exercise pagination logic without a full blueprint."""

    PAGINATION_HEADER_NAME = None


def test_paginate_rejects_non_positive_page() -> None:
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={"page": 0, "page_size": 5})


def test_paginate_rejects_non_positive_page_size() -> None:
    dummy = DummyPagination()

    @dummy.paginate()
    def handler(*args: object, **kwargs: object) -> list[object]:  # pragma: no cover - exercised via wrapper
        return []

    with pytest.raises(BadRequest):
        handler(filters={"page": 1, "page_size": 0})


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
