"""Unit tests for testing helpers in flask_more_smorest.testing module."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flask import Flask

from flask_more_smorest import Api, UserBlueprint, db
from flask_more_smorest.perms.models.defaults import (
    BaseRoleEnum,
    DefaultUser,
    DefaultUserRole,
)
from flask_more_smorest.testing import as_admin, as_user, clear_registration

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


@pytest.fixture
def db_session(unit_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with unit_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def api(unit_api: Api) -> Api:
    """Alias for unit_api to match test method signatures."""
    return unit_api


class TestAsUser:
    """Test as_user context manager."""

    def test_as_user_sets_auth_header(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that as_user sets JWT auth header."""
        # Register user blueprint
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Create test user
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="test@example.com", password="password123")
            user.save()

        # Test that as_user sets the header
        client = unit_app.test_client()
        with as_user(client, str(user.id)):
            response = client.get("/api/users/me/")
            assert response.status_code == 200
            assert response.json is not None
            assert response.json["email"] == "test@example.com"

    def test_as_user_with_additional_claims(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test as_user with additional JWT claims."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with DefaultUser.bypass_perms():
            user = DefaultUser(email="claims@example.com", password="password123")
            user.save()

        client = unit_app.test_client()
        with as_user(client, str(user.id), additional_claims={"tenant_id": "12345"}):
            response = client.get("/api/users/me/")
            assert response.status_code == 200


class TestAsAdmin:
    """Test as_admin context manager."""

    def test_as_admin_sets_auth_header(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that as_admin sets JWT auth header with admin role."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Create admin user
        with DefaultUser.bypass_perms():
            admin = DefaultUser(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(DefaultUserRole(user=admin, role=BaseRoleEnum.ADMIN))

        client = unit_app.test_client()
        with as_admin(client, str(admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

    def test_as_admin_with_superadmin_role(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test as_admin with superadmin role."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with DefaultUser.bypass_perms():
            superadmin = DefaultUser(email="superadmin@example.com", password="password123")
            superadmin.save()
            superadmin.roles.append(DefaultUserRole(user=superadmin, role=BaseRoleEnum.SUPERADMIN))

        client = unit_app.test_client()
        with as_admin(client, str(superadmin.id), roles=["superadmin"]):
            response = client.get("/api/users/")
            assert response.status_code == 200


class TestClearRegistration:
    """Test clear_registration function."""

    def test_clear_registration_resets_to_default(self, unit_app: Flask) -> None:
        """Test that clear_registration resets to default JWT behavior."""
        # This test just verifies the function exists and can be called
        # The actual behavior is tested in test_user_context.py
        clear_registration()
        # No exception means it works
        assert True
