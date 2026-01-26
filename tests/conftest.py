"""Shared pytest fixtures for all tests."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Generator

import pytest

from flask_more_smorest import db
from flask_more_smorest.perms import clear_registration


@pytest.fixture(autouse=True)
def _reset_perms_registry() -> Generator[None, None, None]:
    """Reset perms registry between tests to avoid cross-test leakage."""
    clear_registration()
    yield
    clear_registration()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_mappers() -> Generator[None, None, None]:
    """Clean up SQLAlchemy mappers defined in tests at the end of each module.

    This ensures that test-specific models (like CustomUser in test_user_perms.py)
    are unmapped and removed from the registry, preventing conflicts with other
    tests that might use the default User model with the same table name.
    """
    yield

    # Dispose only test-defined models to avoid unmapping library defaults
    if hasattr(db, "Model") and hasattr(db.Model, "registry"):
        to_dispose = []
        for mapper in list(db.Model.registry.mappers):
            if mapper.class_.__module__.startswith("tests."):
                to_dispose.append(mapper.class_)

        for cls in to_dispose:
            with contextlib.suppress(Exception):
                if hasattr(db.Model.registry, "_dispose_cls"):
                    db.Model.registry._dispose_cls(cls)
            if hasattr(cls, "__table__") and cls.__table__ in db.metadata:
                db.metadata.remove(cls.__table__)

    # Unload cached user schemas to avoid stale BaseUserSchema
    if "flask_more_smorest.perms.user_schemas" in sys.modules:
        del sys.modules["flask_more_smorest.perms.user_schemas"]
