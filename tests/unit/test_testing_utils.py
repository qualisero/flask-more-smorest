"""Tests for testing utilities."""

import uuid

from tests.testing_utils import (
    _create_mock_user,
    as_admin,
    as_anonymous,
    as_superadmin,
    as_user,
)


class TestMockUserCreation:
    """Tests for _create_mock_user helper."""

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
        assert not user.has_role("admin")
        assert not user.has_role("superadmin")

    def test_admin_user_has_admin_role(self) -> None:
        user = _create_mock_user(is_admin=True)
        assert user.is_admin
        assert not user.is_superadmin
        assert user.has_role("admin")
        assert not user.has_role("superadmin")

    def test_superadmin_user_has_both_roles(self) -> None:
        user = _create_mock_user(is_superadmin=True)
        assert user.is_admin  # superadmin implies admin
        assert user.is_superadmin
        assert user.has_role("admin")
        assert user.has_role("superadmin")

    def test_list_roles_regular_user(self) -> None:
        user = _create_mock_user()
        assert user.list_roles() == ["user"]

    def test_list_roles_admin(self) -> None:
        user = _create_mock_user(is_admin=True)
        assert "admin" in user.list_roles()

    def test_list_roles_superadmin(self) -> None:
        user = _create_mock_user(is_superadmin=True)
        roles = user.list_roles()
        assert "superadmin" in roles
        assert "admin" in roles


class TestAsUserContextManager:
    """Tests for as_user context manager."""

    def test_as_user_sets_current_user(self, app) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        mock_user = _create_mock_user()

        with app.app_context():
            with as_user(mock_user):
                current = get_current_user()
                assert current is mock_user

    def test_as_user_restores_previous_getter(self, app) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            original = get_current_user()
            with as_user(_create_mock_user()):
                pass
            after = get_current_user()
            # Both should be None (no JWT context)
            assert original is None
            assert after is None

    def test_as_user_with_none(self, app) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            with as_user(None):
                assert get_current_user() is None


class TestAsAdminContextManager:
    """Tests for as_admin context manager."""

    def test_as_admin_sets_admin_user(self, app) -> None:
        from flask_more_smorest.perms.user_context import get_current_user, is_current_user_admin

        with app.app_context():
            with as_admin() as admin:
                current = get_current_user()
                assert current is admin
                assert is_current_user_admin()

    def test_as_admin_yields_mock(self, app) -> None:
        with app.app_context():
            with as_admin() as admin:
                assert admin.is_admin
                assert admin.has_role("admin")

    def test_as_admin_with_custom_id(self, app) -> None:
        custom_id = uuid.uuid4()
        with app.app_context():
            with as_admin(user_id=custom_id) as admin:
                assert admin.id == custom_id


class TestAsSuperadminContextManager:
    """Tests for as_superadmin context manager."""

    def test_as_superadmin_sets_superadmin_user(self, app) -> None:
        from flask_more_smorest.perms.user_context import (
            get_current_user,
            is_current_user_superadmin,
        )

        with app.app_context():
            with as_superadmin() as superadmin:
                current = get_current_user()
                assert current is superadmin
                assert is_current_user_superadmin()

    def test_as_superadmin_yields_mock(self, app) -> None:
        with app.app_context():
            with as_superadmin() as superadmin:
                assert superadmin.is_superadmin
                assert superadmin.has_role("superadmin")


class TestAsAnonymousContextManager:
    """Tests for as_anonymous context manager."""

    def test_as_anonymous_clears_user(self, app) -> None:
        from flask_more_smorest.perms.user_context import get_current_user

        with app.app_context():
            with as_anonymous():
                assert get_current_user() is None

    def test_as_anonymous_admin_check_fails(self, app) -> None:
        from flask_more_smorest.perms.user_context import is_current_user_admin

        with app.app_context():
            with as_anonymous():
                assert not is_current_user_admin()
