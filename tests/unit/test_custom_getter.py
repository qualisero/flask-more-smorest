"""Unit tests for extending User model with custom get_current_user mechanism.

Tests focus on the registration and behavior of custom get_current_user functions.
"""

import contextlib
import sys
import uuid
from collections.abc import Generator

import pytest
import sqlalchemy as sa
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import db, init_db, init_jwt
from flask_more_smorest.perms import (
    clear_registration,
    init_fms,
    is_current_user_admin,
    is_current_user_superadmin,
)
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.models.abstract_user import AbstractUser


def build_models() -> type[AbstractUser]:
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    import sys
    import types

    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomUser(AbstractUser):  # type: ignore[misc]
        __module__ = module_name
        __allow_unmapped__ = True

        external_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
        source_system: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    return CustomUser


def reset_models() -> None:
    clear_registration()
    with contextlib.suppress(Exception):
        sa.orm.clear_mappers()
    db.metadata.clear()
    modules_to_unload = [
        "flask_more_smorest.perms.models.role",
        "flask_more_smorest.perms.models.token",
        "flask_more_smorest.perms.models.setting",
        "flask_more_smorest.perms.models.defaults",
        "flask_more_smorest.perms.models.user",
        "flask_more_smorest.perms.user_schemas",
    ]
    for module_name in modules_to_unload:
        sys.modules.pop(module_name, None)


@pytest.fixture(autouse=True)
def _clear_registration() -> Generator[None, None, None]:
    reset_models()
    yield
    reset_models()


@pytest.fixture
def unit_app() -> Generator[Flask, None, None]:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key"

    init_db(app)
    init_jwt(app)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def db_session(unit_app: Flask) -> Generator[None, None, None]:
    with unit_app.app_context():
        yield
        db.session.remove()
        db.drop_all()


class TestCustomGetter:
    """Test extending User model with custom get_current_user mechanism."""

    def test_init_fms_with_custom_getter(self, unit_app: Flask, db_session: Generator[None, None, None]) -> None:
        """Test that init_fms with custom getter works."""
        CustomUser = build_models()

        clear_registration()
        init_fms(user=CustomUser)
        db.create_all()

        # Create a test user in database with extra attributes
        with CustomUser.bypass_perms():
            user = CustomUser(
                email="external@example.com",
                password="password123",
            )
            user.external_id = "EXT123"  # type: ignore[attr-defined]
            user.source_system = "LDAP"  # type: ignore[attr-defined]
            user.save()

        # Mock external authentication
        def external_get_user() -> CustomUser | None:  # type: ignore[valid-type]
            """Simulate external auth (LDAP, OAuth, etc.)."""
            return db.session.query(CustomUser).filter_by(email="external@example.com").first()

        # Register custom getter
        init_fms(get_current_user=external_get_user)

        # Custom getter should be used
        current = CustomUser.get_current_user()
        assert current is not None
        assert isinstance(current, CustomUser)
        assert current.external_id == "EXT123"  # type: ignore[attr-defined]
        assert current.source_system == "LDAP"  # type: ignore[attr-defined]

    def test_custom_getter_overrides_jwt_fallback(
        self, unit_app: Flask, db_session: Generator[None, None, None]
    ) -> None:
        """Test that custom getter takes precedence over JWT."""
        CustomUser = build_models()

        clear_registration()
        init_fms(user=CustomUser)
        db.create_all()

        # Create test users
        with CustomUser.bypass_perms():
            jwt_user = CustomUser(email="jwt@example.com", password="password123")
            jwt_user.save()

            custom_user = CustomUser(email="custom@example.com", password="password123")
            custom_user.save()

        # Register custom getter that always returns custom_user
        def custom_get_user() -> CustomUser | None:  # type: ignore[valid-type]
            return db.session.query(CustomUser).filter_by(email="custom@example.com").first()

        init_fms(get_current_user=custom_get_user)

        # Custom getter should override JWT
        current = CustomUser.get_current_user()
        assert current is not None
        assert current.email == "custom@example.com"

    def test_custom_getter_returns_none(self, unit_app: Flask, db_session: Generator[None, None, None]) -> None:
        """Test that custom getter returning None is handled correctly."""
        CustomUser = build_models()

        clear_registration()
        init_fms(user=CustomUser)

        # Custom getter returns None
        def unauthenticated_get_user() -> CustomUser | None:  # type: ignore[valid-type]
            return None

        init_fms(get_current_user=unauthenticated_get_user)

        # Should return None when no user authenticated
        current = CustomUser.get_current_user()
        assert current is None

    def test_custom_getter_with_roles(self, unit_app: Flask, db_session: Generator[None, None, None]) -> None:
        """Test custom getter with role checks."""
        CustomUser = build_models()

        clear_registration()
        init_fms(user=CustomUser)
        db.create_all()

        # Create test user with admin role
        with CustomUser.bypass_perms():
            user = CustomUser(email="admin@example.com", password="password123")
            user.save()
            user.roles.append(defaults_module.UserRole(user=user, role=defaults_module.BaseRoleEnum.ADMIN))

        # Custom getter returns admin user
        def get_admin() -> CustomUser | None:  # type: ignore[valid-type]
            return db.session.query(CustomUser).filter_by(email="admin@example.com").first()

        init_fms(get_current_user=get_admin)

        # Test role checks
        assert is_current_user_admin() is True
        assert is_current_user_superadmin() is False
