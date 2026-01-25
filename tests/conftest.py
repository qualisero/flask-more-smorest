"""Shared pytest fixtures for all tests."""

from __future__ import annotations

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

    # Cleanup SQLAlchemy mappers defined in tests
    if hasattr(db, "Model") and hasattr(db.Model, "registry"):
        to_dispose = []
        for mapper in db.Model.registry.mappers:
            # Check if class is defined in a test module
            # We specifically target models defined in the tests/ package
            if mapper.class_.__module__.startswith("tests."):
                to_dispose.append(mapper.class_)

        for cls in to_dispose:
            # Remove from registry using internal method if available
            if hasattr(db.Model.registry, "_dispose_cls"):
                db.Model.registry._dispose_cls(cls)

            # Remove table from metadata to allow re-creation
            if hasattr(cls, "__table__") and cls.__table__ in db.metadata:
                db.metadata.remove(cls.__table__)
