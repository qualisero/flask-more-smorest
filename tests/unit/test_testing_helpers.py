"""Unit tests for testing helpers in flask_more_smorest.testing module."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flask import Flask

from flask_more_smorest import Api, User, UserBlueprint, db
from flask_more_smorest.perms.models import DefaultUserRole, UserRole
from flask_more_smorest.testing import as_admin, as_user, clear_registration

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


@pytest.fixture(scope="function")
def db_session(unit_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with unit_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
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
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Test that as_user sets the header
        client = unit_app.test_client()
        with as_user(client, str(user.id)):
            response = client.get("/api/users/me/")
            assert response.status_code == 200
            assert response.json["email"] == "test@example.com"

    def test_as_user_with_additional_claims(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test as_user with additional JWT claims."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with User.bypass_perms():
            user = User(email="claims@example.com", password="password123")
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
        with User.bypass_perms():
            admin = User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=DefaultUserRole.ADMIN))

        client = unit_app.test_client()
        with as_admin(client, str(admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

    def test_as_admin_with_superadmin_role(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test as_admin with superadmin role."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with User.bypass_perms():
            superadmin = User(email="superadmin@example.com", password="password123")
            superadmin.save()
            superadmin.roles.append(UserRole(user=superadmin, role=DefaultUserRole.SUPERADMIN))

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
