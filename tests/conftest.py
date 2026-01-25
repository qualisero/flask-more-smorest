"""Shared pytest fixtures for all tests."""

from __future__ import annotations

import sys
from collections.abc import Generator

import pytest
from sqlalchemy.orm import clear_mappers

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

    # Clear all mappers to ensure a clean slate for the next test module
    clear_mappers()

    # Clear metadata to remove table definitions
    if hasattr(db, "metadata"):
        db.metadata.clear()

    # Force re-import of persistent model modules to re-map them
    # This is necessary because clear_mappers() leaves classes unmapped
    modules_to_unload = [
        "flask_more_smorest.perms.models.role",
        "flask_more_smorest.perms.models.token",
        "flask_more_smorest.perms.models.setting",
        "flask_more_smorest.perms.models.defaults",
        "flask_more_smorest.perms.models.user",
    ]

    for module_name in modules_to_unload:
        if module_name in sys.modules:
            del sys.modules[module_name]
