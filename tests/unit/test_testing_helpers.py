"""Tests for testing helpers in flask_more_smorest.testing module.

This file contains both unit tests (with mocks) and integration tests (with real Flask app).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flask import Flask

from flask_more_smorest import Api, UserBlueprint, db
from flask_more_smorest.perms.models import defaults as defaults_module

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


# Import unit test utilities (mocks, no JWT)
# Import integration test utilities (real Flask app, JWT)
from flask_more_smorest.testing import (
    as_admin,  # Real JWT version
    as_user,  # Real JWT version
    clear_registration,
)
from tests.testing_utils import (
    _create_mock_user,
    as_anonymous,
    as_superadmin,
)
from tests.testing_utils import (
    as_admin as as_admin_mocked,  # Mock version
)
from tests.testing_utils import (
    as_user as as_user_mocked,  # Mock version
)


@pytest.fixture
def db_session(unit_app: Flask) -> Iterator[scoped_session]:
    """Create a database session for integration tests."""
    with unit_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def api(unit_api: Api) -> Api:
    """Alias for unit_api to match test method signatures."""
    return unit_api


# =============================================================================
# SECTION 1: Unit Tests (using mocks, no database, no JWT)
# =============================================================================


class TestMockUserCreation:
    """Tests for _create_mock_user helper - UNIT TESTS."""

    def test_creates_user_with_id(self) -> None:
        user = _create_mock_user()
        assert isinstance(user.id, uuid.UUID)

    def test_creates_user_with_custom_id(self) -> None:
        custom_id = uuid.uuid4()
        user = _create_mock_user(user_id=custom_id)
        assert user.id == custom_id

    def test_regular_user_has_no_admin_role(self) -> None:
        user = _create_mock_user()
        assert not user.is_admin
        assert not user.is_superadmin
        assert not user.has_role("ADMIN")
        assert not user.has_role("SUPERADMIN")

    def test_admin_user_has_admin_role(self) -> None:
        user = _create_mock_user(is_admin=True)
        assert user.is_admin
        assert not user.is_superadmin
        assert user.has_role("ADMIN")
        assert not user.has_role("SUPERADMIN")

    def test_superadmin_user_has_both_roles(self) -> None:
        user = _create_mock_user(is_superadmin=True)
        assert user.is_admin  # superadmin implies admin
        assert user.is_superadmin
        assert user.has_role("admin")
        assert user.has_role("superadmin")

    def test_list_roles_regular_user(self) -> None:
        user = _create_mock_user()
        assert user.list_roles() == ["USER"]

    def test_list_roles_admin(self) -> None:
        user = _create_mock_user(is_admin=True)
        assert "ADMIN" in user.list_roles()

    def test_list_roles_superadmin(self) -> None:
        user = _create_mock_user(is_superadmin=True)
        roles = user.list_roles()
        assert "SUPERADMIN" in roles
        assert "ADMIN" in roles


class TestAsUserContextManager:
    """Tests for as_user context manager - UNIT TESTS (mocks, no JWT)."""

    def test_as_user_sets_current_user(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        mock_user = _create_mock_user()

        with app.app_context():
            with as_user_mocked(mock_user):
                current = get_current_user()
                assert current is mock_user

    def test_as_user_restores_previous_getter(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            original = get_current_user()
            with as_user_mocked(_create_mock_user()):
                pass
            after = get_current_user()
            # Both should be None (no JWT context)
            assert original is None
            assert after is None

    def test_as_user_with_none(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            with as_user_mocked(None):
                assert get_current_user() is None


class TestAsAdminContextManager:
    """Tests for as_admin context manager - UNIT TESTS (mocks, no JWT)."""

    def test_as_admin_sets_admin_user(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import get_current_user, is_current_user_admin

        with app.app_context():
            with as_admin_mocked() as admin:
                current = get_current_user()
                assert current is admin
                assert is_current_user_admin()

    def test_as_admin_yields_mock(self, app: Flask) -> None:
        with app.app_context():
            with as_admin_mocked() as admin:
                assert admin.is_admin
                assert admin.has_role("ADMIN")

    def test_as_admin_with_custom_id(self, app: Flask) -> None:
        custom_id = uuid.uuid4()
        with app.app_context():
            with as_admin_mocked(user_id=custom_id) as admin:
                assert admin.id == custom_id


class TestAsSuperadminContextManager:
    """Tests for as_superadmin context manager - UNIT TESTS (mocks, no JWT)."""

    def test_as_superadmin_sets_superadmin_user(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import (
            get_current_user,
            is_current_user_superadmin,
        )

        with app.app_context():
            with as_superadmin() as superadmin:
                current = get_current_user()
                assert current is superadmin
                assert is_current_user_superadmin()

    def test_as_superadmin_yields_mock(self, app: Flask) -> None:
        with app.app_context():
            with as_superadmin() as superadmin:
                assert superadmin.is_superadmin
                assert superadmin.has_role("superadmin")


class TestAsAnonymousContextManager:
    """Tests for as_anonymous context manager - UNIT TESTS (mocks, no JWT)."""

    def test_as_anonymous_clears_user(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            with as_anonymous():
                assert get_current_user() is None

    def test_as_anonymous_admin_check_fails(self, app: Flask) -> None:
        from flask_more_smorest.perms.user_context import is_current_user_admin

        with app.app_context():
            with as_anonymous():
                assert not is_current_user_admin()


# =============================================================================
# SECTION 2: Integration Tests (real Flask app, database, JWT tokens)
# =============================================================================


class TestAsUserIntegration:
    """Test as_user context manager - INTEGRATION TESTS."""

    def test_as_user_sets_auth_header(self, unit_app: Flask, api: Api, db_session: scoped_session) -> None:
        """Test that as_user sets JWT auth header."""
        # Register user blueprint
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Create test user
        with defaults_module.User.bypass_perms():
            user = defaults_module.User(email="test@example.com", password="password123")
            user.save()

        # Test that as_user sets the header
        client = unit_app.test_client()
        with as_user(client, str(user.id)):
            response = client.get("/api/users/me")
            assert response.status_code == 200
            assert response.json is not None
            assert response.json["email"] == "test@example.com"

    def test_as_user_with_additional_claims(self, unit_app: Flask, api: Api, db_session: scoped_session) -> None:
        """Test as_user with additional JWT claims."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with defaults_module.User.bypass_perms():
            user = defaults_module.User(email="claims@example.com", password="password123")
            user.save()

        client = unit_app.test_client()
        with as_user(client, str(user.id), additional_claims={"tenant_id": "12345"}):
            response = client.get("/api/users/me")
            assert response.status_code == 200


class TestAsAdminIntegration:
    """Test as_admin context manager - INTEGRATION TESTS."""

    def test_as_admin_sets_auth_header(self, unit_app: Flask, api: Api, db_session: scoped_session) -> None:
        """Test that as_admin sets JWT auth header with admin role."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Create admin user
        with defaults_module.User.bypass_perms():
            admin = defaults_module.User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(defaults_module.UserRole(user=admin, role=defaults_module.BaseRoleEnum.ADMIN))

        client = unit_app.test_client()
        with as_admin(client, str(admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

    def test_as_admin_with_superadmin_role(self, unit_app: Flask, api: Api, db_session: scoped_session) -> None:
        """Test as_admin with superadmin role."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        with defaults_module.User.bypass_perms():
            superadmin = defaults_module.User(email="superadmin@example.com", password="password123")
            superadmin.save()
            superadmin.roles.append(
                defaults_module.UserRole(user=superadmin, role=defaults_module.BaseRoleEnum.SUPERADMIN)
            )

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
