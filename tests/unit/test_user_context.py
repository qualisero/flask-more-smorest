"""Unit tests for flask_more_smorest.perms.user_context module."""

import uuid
from typing import Any

from flask import Flask

from flask_more_smorest.perms.user_context import (
    GetCurrentUserFunc,
    GetCurrentUserIdFunc,
    IsCurrentUserAdminFunc,
    UserProtocol,
    clear_registrations,
    get_current_user,
    get_current_user_id,
    is_current_user_admin,
    register_get_current_user,
    register_get_current_user_id,
    register_is_current_user_admin,
)


class TestUserProtocol:
    """Test UserProtocol for type checking."""

    def test_user_protocol_checks_valid_user(self) -> None:
        """Test that UserProtocol correctly identifies conforming objects."""

        class ValidUser:
            def __init__(self) -> None:
                self.id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return True

        user = ValidUser()
        assert isinstance(user, UserProtocol)

    def test_user_protocol_rejects_invalid_user(self) -> None:
        """Test that UserProtocol rejects non-conforming objects."""

        class InvalidUser:
            def __init__(self) -> None:
                self.email = "test@example.com"

        user = InvalidUser()
        assert not isinstance(user, UserProtocol)

    def test_user_protocol_checks_is_admin_property(self) -> None:
        """Test that UserProtocol requires is_admin as property."""

        class UserWithoutIsAdmin:
            def __init__(self) -> None:
                self.id = uuid.uuid4()

        user = UserWithoutIsAdmin()
        assert not isinstance(user, UserProtocol)


class TestRegistrationFunctions:
    """Test registration functions for user context."""

    def setup_method(self) -> None:
        """Clear registrations before each test."""
        clear_registrations()

    def teardown_method(self) -> None:
        """Clear registrations after each test."""
        clear_registrations()

    def test_register_get_current_user(self) -> None:
        """Test registering custom get_current_user function."""
        test_user = {"id": "test-user"}

        def my_get_user() -> Any:
            return test_user

        register_get_current_user(my_get_user)

        # Get current user should use registered function
        result = get_current_user()
        assert result == test_user

    def test_register_get_current_user_id(self) -> None:
        """Test registering custom get_current_user_id function."""
        test_id = uuid.uuid4()

        def my_get_user_id() -> uuid.UUID | None:
            return test_id

        register_get_current_user_id(my_get_user_id)

        # Should use registered function
        result = get_current_user_id()
        assert result == test_id

    def test_register_is_current_user_admin(self) -> None:
        """Test registering custom is_current_user_admin function."""

        def my_admin_check() -> bool:
            return True

        register_is_current_user_admin(my_admin_check)

        # Should use registered function
        assert is_current_user_admin() is True

    def test_clear_registrations_removes_all(self) -> None:
        """Test that clear_registrations removes all registered functions."""

        def my_func() -> Any:
            return "test"

        register_get_current_user(my_func)
        register_get_current_user_id(my_func)  # type: ignore
        register_is_current_user_admin(my_func)  # type: ignore

        clear_registrations()

        # Should fall back to built-in behavior (returns None outside request context)
        result = get_current_user()
        assert result is None


class TestGetCurrentUser:
    """Test get_current_user resolution."""

    def setup_method(self) -> None:
        """Clear registrations before each test."""
        clear_registrations()

    def teardown_method(self) -> None:
        """Clear registrations after each test."""
        clear_registrations()

    def test_flask_config_takes_precedence(self, app: Flask) -> None:
        """Test that Flask config takes precedence over global registration."""
        config_user = {"id": "config-user"}
        global_user = {"id": "global-user"}

        def config_func() -> Any:
            return config_user

        def global_func() -> Any:
            return global_user

        register_get_current_user(global_func)
        app.config["FMS_GET_CURRENT_USER"] = config_func

        with app.app_context():
            result = get_current_user()
            assert result == config_user

    def test_global_registration_used_when_no_config(self) -> None:
        """Test that global registration is used when no Flask config."""
        test_user = {"id": "global-user"}

        def global_func() -> Any:
            return test_user

        register_get_current_user(global_func)

        result = get_current_user()
        assert result == test_user

    def test_fallback_to_builtin_when_no_registration(self) -> None:
        """Test fallback to built-in user_models when nothing registered."""
        # Outside request context, built-in returns None
        result = get_current_user()
        assert result is None

    def test_config_none_value_skipped(self, app: Flask) -> None:
        """Test that None config value doesn't override registration."""
        test_user = {"id": "global-user"}

        def global_func() -> Any:
            return test_user

        register_get_current_user(global_func)
        app.config["FMS_GET_CURRENT_USER"] = None

        with app.app_context():
            # Should skip None config and use global
            result = get_current_user()
            assert result == test_user


class TestGetCurrentUserId:
    """Test get_current_user_id resolution."""

    def setup_method(self) -> None:
        """Clear registrations before each test."""
        clear_registrations()

    def teardown_method(self) -> None:
        """Clear registrations after each test."""
        clear_registrations()

    def test_flask_config_takes_precedence(self, app: Flask) -> None:
        """Test that Flask config takes precedence over global registration."""
        config_id = uuid.uuid4()
        global_id = uuid.uuid4()

        def config_func() -> uuid.UUID:
            return config_id

        def global_func() -> uuid.UUID:
            return global_id

        register_get_current_user_id(global_func)
        app.config["FMS_GET_CURRENT_USER_ID"] = config_func

        with app.app_context():
            result = get_current_user_id()
            assert result == config_id

    def test_global_registration_used_when_no_config(self) -> None:
        """Test that global registration is used when no Flask config."""
        test_id = uuid.uuid4()

        def global_func() -> uuid.UUID:
            return test_id

        register_get_current_user_id(global_func)

        result = get_current_user_id()
        assert result == test_id

    def test_returns_none_when_no_user(self) -> None:
        """Test that None is returned when no user authenticated."""

        def no_user_func() -> None:
            return None

        register_get_current_user_id(no_user_func)

        result = get_current_user_id()
        assert result is None

    def test_fallback_to_builtin_when_no_registration(self) -> None:
        """Test fallback to built-in user_models when nothing registered."""
        # Outside request context, built-in returns None
        result = get_current_user_id()
        assert result is None


class TestIsCurrentUserAdmin:
    """Test is_current_user_admin resolution."""

    def setup_method(self) -> None:
        """Clear registrations before each test."""
        clear_registrations()

    def teardown_method(self) -> None:
        """Clear registrations after each test."""
        clear_registrations()

    def test_flask_config_takes_precedence(self, app: Flask) -> None:
        """Test that Flask config takes precedence over global registration."""

        def config_func() -> bool:
            return True

        def global_func() -> bool:
            return False

        register_is_current_user_admin(global_func)
        app.config["FMS_IS_CURRENT_USER_ADMIN"] = config_func

        with app.app_context():
            result = is_current_user_admin()
            assert result is True

    def test_global_registration_used_when_no_config(self) -> None:
        """Test that global registration is used when no Flask config."""

        def admin_check() -> bool:
            return True

        register_is_current_user_admin(admin_check)

        result = is_current_user_admin()
        assert result is True

    def test_fallback_checks_user_is_admin_attribute(self) -> None:
        """Test fallback checks user.is_admin when no registration."""

        class MockUser:
            is_admin = True

        def get_user() -> MockUser:
            return MockUser()

        register_get_current_user(get_user)

        result = is_current_user_admin()
        assert result is True

    def test_fallback_returns_false_when_no_is_admin(self) -> None:
        """Test fallback returns False when user has no is_admin attribute."""

        class MockUser:
            pass

        def get_user() -> MockUser:
            return MockUser()

        register_get_current_user(get_user)

        result = is_current_user_admin()
        assert result is False

    def test_fallback_returns_false_when_no_user(self) -> None:
        """Test fallback returns False when no user authenticated."""

        def get_user() -> None:
            return None

        register_get_current_user(get_user)

        result = is_current_user_admin()
        assert result is False

    def test_exception_handling_returns_false(self) -> None:
        """Test that exceptions in fallback (not registration) return False."""
        # Test the fallback's exception handling by using get_current_user
        # that raises an exception

        def failing_get_user() -> Any:
            raise ValueError("Test error")

        register_get_current_user(failing_get_user)
        # Don't register is_current_user_admin, so it uses fallback

        # Fallback will call get_current_user (which raises), catch it, return False
        result = is_current_user_admin()
        assert result is False


class TestIntegrationWithFlaskConfig:
    """Test integration with Flask application configuration."""

    def setup_method(self) -> None:
        """Clear registrations before each test."""
        clear_registrations()

    def teardown_method(self) -> None:
        """Clear registrations after each test."""
        clear_registrations()

    def test_all_three_config_options_work_together(self, app: Flask) -> None:
        """Test that all three config options can be set together."""
        test_user = {"id": "test-user", "is_admin": True}
        test_id = uuid.uuid4()

        def get_user() -> dict:
            return test_user

        def get_id() -> uuid.UUID:
            return test_id

        def check_admin() -> bool:
            return True

        app.config["FMS_GET_CURRENT_USER"] = get_user
        app.config["FMS_GET_CURRENT_USER_ID"] = get_id
        app.config["FMS_IS_CURRENT_USER_ADMIN"] = check_admin

        with app.app_context():
            assert get_current_user() == test_user
            assert get_current_user_id() == test_id
            assert is_current_user_admin() is True

    def test_partial_config_uses_fallback_for_rest(self, app: Flask) -> None:
        """Test that partial config uses fallback for unset options."""
        test_id = uuid.uuid4()

        def get_id() -> uuid.UUID:
            return test_id

        app.config["FMS_GET_CURRENT_USER_ID"] = get_id
        # Don't set the other two

        with app.app_context():
            assert get_current_user_id() == test_id
            # These should use built-in fallback (returns None outside request context)
            result = get_current_user()
            assert result is None


class TestTypeSafety:
    """Test type annotations and signatures."""

    def test_get_current_user_func_type(self) -> None:
        """Test GetCurrentUserFunc type annotation."""

        def valid_func() -> Any:
            return None

        # Should be assignable
        func: GetCurrentUserFunc = valid_func
        assert callable(func)

    def test_get_current_user_id_func_type(self) -> None:
        """Test GetCurrentUserIdFunc type annotation."""

        def valid_func() -> uuid.UUID | None:
            return None

        # Should be assignable
        func: GetCurrentUserIdFunc = valid_func
        assert callable(func)

    def test_is_current_user_admin_func_type(self) -> None:
        """Test IsCurrentUserAdminFunc type annotation."""

        def valid_func() -> bool:
            return False

        # Should be assignable
        func: IsCurrentUserAdminFunc = valid_func
        assert callable(func)
