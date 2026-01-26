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

    # Clear Flask-SQLAlchemy's declarative class registry
    # This prevents "already contains a class" warnings on re-import
    if hasattr(db.Model, "_decl_class_registry"):
        db.Model._decl_class_registry.clear()

    # Clear SQLAlchemy's mapper registry state
    # This is necessary to fully reset mapper configuration
    with contextlib.suppress(Exception):
        from sqlalchemy.orm import clear_mappers

        clear_mappers()
        # Also clear the mapper's internal state
        if hasattr(db.Model, "__mapper__"):
            mapper_registry = getattr(db.Model.metadata, "_sa_registry", None)
            if mapper_registry is not None and hasattr(mapper_registry, "_mappers"):
                mapper_registry._mappers.clear()

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
        "flask_more_smorest.perms.user_schemas",
    ]

    for module_name in modules_to_unload:
        if module_name in sys.modules:
            del sys.modules[module_name]
