"""Unit tests for flask-more-smorest.perms.user_context module."""

import uuid

import pytest

from flask_more_smorest.perms.user_context import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    AdminRole,
    UserProtocol,
    clear_registration,
    get_current_user,
    get_current_user_id,
    is_current_user_admin,
    is_current_user_superadmin,
    register_user_class,
)


class TestUserProtocol:
    """Test UserProtocol for type checking."""

    def test_user_protocol_checks_valid_user(self) -> None:
        """Test that UserProtocol correctly identifies conforming objects."""

        class ValidUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_ADMIN

            def list_roles(self) -> list[str]:
                return [ROLE_ADMIN]

        user = ValidUser()
        assert isinstance(user, UserProtocol)


@pytest.mark.usefixtures("reset_user_context")
class TestRegistrationFunctions:
    """Test registration functions for user context."""

    def test_register_user_class(self) -> None:
        """Test registering custom user class with custom getter."""

        class MyUser:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.id = user_id

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        user_id = uuid.uuid4()
        test_user = MyUser(user_id)

        def my_get_user() -> MyUser | None:
            return test_user

        register_user_class(MyUser, get_current_user=my_get_user)

        # Get current user should use registered function
        result = get_current_user(MyUser)
        assert result is test_user

    def test_clear_registration_removes_registration(self) -> None:
        """Test that clear_registration removes registered function."""

        class MyUser:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.id = user_id

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        def my_func() -> MyUser | None:
            return MyUser(uuid.uuid4())

        register_user_class(MyUser, get_current_user=my_func)
        clear_registration()

        # Call clear_registration to verify it removes registration
        # Should fall back to built-in (returns None outside Flask context)
        result = get_current_user(MyUser)
        assert result is None


@pytest.mark.usefixtures("reset_user_context")
class TestGetCurrentUser:
    """Test get_current_user resolution."""

    def test_global_registration_used_when_registered(self) -> None:
        """Test that global registration is used when registered."""

        class MyUser:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.id = user_id

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        test_user = MyUser(uuid.uuid4())

        def global_func() -> MyUser | None:
            return test_user

        register_user_class(MyUser, get_current_user=global_func)

        result = get_current_user(MyUser)
        assert result is test_user

    def test_fallback_to_builtin_when_no_registration(self) -> None:
        """Test fallback to built-in models when nothing registered."""
        # Outside Flask context, built-in returns None
        result = get_current_user()
        assert result is None

    def test_user_type_filter_returns_none_on_mismatch(self) -> None:
        """Test that providing user_type returns None if user is not that type."""

        class MyUser:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.id = user_id

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        class OtherUser:
            def __init__(self, user_id: uuid.UUID) -> None:
                self.id = user_id

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        test_user = MyUser(uuid.uuid4())

        def my_get_user() -> MyUser | None:
            return test_user

        # Register MyUser but request OtherUser type
        register_user_class(MyUser, get_current_user=my_get_user)

        # Requesting specific type should return None
        result = get_current_user(OtherUser)
        assert result is None


@pytest.mark.usefixtures("reset_user_context")
class TestGetCurrentUserId:
    """Test get_current_user_id extraction from user."""

    def test_get_current_user_id(self) -> None:
        """Test get_current_user_id extracts ID correctly."""
        user_id = uuid.uuid4()

        class User:
            def __init__(self, value: uuid.UUID) -> None:
                self.id = value

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        def my_get_user() -> User | None:
            return User(user_id)

        register_user_class(User, get_current_user=my_get_user)

        result = get_current_user_id()
        assert result == user_id


@pytest.mark.usefixtures("reset_user_context")
class TestIsCurrentUserAdmin:
    """Test is_current_user_admin extraction from user."""

    def test_is_current_user_admin_with_has_role_admin(self) -> None:
        """Test is_current_user_admin uses has_role for admin."""

        class RoleUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_ADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(RoleUser, get_current_user=lambda: RoleUser())
        assert is_current_user_admin() is True

    def test_is_current_user_admin_with_has_role_superadmin(self) -> None:
        """Test is_current_user_admin returns True for superadmin role."""

        class RoleUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_SUPERADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(RoleUser, get_current_user=lambda: RoleUser())
        assert is_current_user_admin() is True

    def test_is_current_user_admin_with_has_role_none(self) -> None:
        """Test is_current_user_admin returns False when no admin roles."""

        class RoleUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        register_user_class(RoleUser, get_current_user=lambda: RoleUser())
        assert is_current_user_admin() is False

    def test_is_current_user_admin_no_user(self) -> None:
        """Test is_current_user_admin returns False when no user is present."""

        class MockUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        register_user_class(MockUser, get_current_user=lambda: None)
        assert is_current_user_admin() is False


@pytest.mark.usefixtures("reset_user_context")
class TestIsCurrentUserSuperadmin:
    """Test is_current_user_superadmin extraction from user."""

    def test_is_current_user_superadmin_with_has_role(self) -> None:
        """Test is_current_user_superadmin uses has_role when available."""

        class RoleUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_SUPERADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(RoleUser, get_current_user=lambda: RoleUser())
        assert is_current_user_superadmin() is True

    def test_is_current_user_superadmin_with_has_role_admin_only(self) -> None:
        """Test is_current_user_superadmin returns False for admin-only role."""

        class RoleUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_ADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(RoleUser, get_current_user=lambda: RoleUser())
        assert is_current_user_superadmin() is False

    def test_is_current_user_superadmin_no_user(self) -> None:
        """Test is_current_user_superadmin returns False when no user is present."""

        class MockUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return False

            def list_roles(self) -> list[str]:
                return []

        register_user_class(MockUser, get_current_user=lambda: None)
        assert is_current_user_superadmin() is False


@pytest.mark.usefixtures("reset_user_context")
class TestTypeSafety:
    """Test type safety with UserProtocol."""

    def test_user_protocol_with_valid_user(self) -> None:
        """Test UserProtocol with valid user."""

        class ValidUser:
            id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_ADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(ValidUser, get_current_user=lambda: ValidUser())
        assert get_current_user() is not None

    def test_user_protocol_with_object_user(self) -> None:
        """Test UserProtocol works with object attribute access."""

        class ObjectUser:
            def __init__(self) -> None:
                self.id = uuid.uuid4()

            @property
            def is_admin(self) -> bool:
                return False

            @property
            def is_superadmin(self) -> bool:
                return False

            def has_role(self, role: AdminRole) -> bool:
                return role == ROLE_ADMIN

            def list_roles(self) -> list[str]:
                return []

        register_user_class(ObjectUser, get_current_user=lambda: ObjectUser())
        assert get_current_user() is not None
