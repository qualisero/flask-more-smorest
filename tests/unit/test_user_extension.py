"""Unit tests for extending User model with custom columns/perms."""

import pytest

from flask_more_smorest.perms import (
    User,
    is_current_user_admin,
    is_current_user_superadmin,
    register_user_class,
)
from flask_more_smorest.perms.models import DefaultUserRole, UserRole


@pytest.mark.usefixtures("reset_user_context")
class TestUserExtension:
    """Test extending User model with custom columns and perms."""

    def test_user_extension_with_custom_columns(self, unit_app) -> None:
        """Test that custom User subclass with extra columns works."""

        class CustomFieldsUser(User):
            """Custom user with extra fields."""

            employee_id = "EMP001"
            department = "Engineering"
            salary = 100000

        user = CustomFieldsUser(
            email="custom@example.com",
            password="password123",
        )
        assert user.employee_id == "EMP001"
        assert user.department == "Engineering"
        assert user.salary == 100000

    def test_user_extension_with_custom_permissions(self, unit_app) -> None:
        """Test that custom User subclass with overridden permissions works."""

        class AgeRestrictedUser(User):
            """User with age-based permission restrictions."""

            __allow_unmapped__ = True
            age: int | None = None

            def _can_write(self, current_user) -> bool:
                """Minors cannot edit their profile.

                Args:
                    current_user: The current authenticated user, or None
                """
                # Check age restriction directly
                if hasattr(self, "age") and self.age is not None and self.age < 18:
                    return False  # Minors can't edit
                # Defer to parent for bypass and other checks
                return super()._can_write(current_user)

        restricted_user = AgeRestrictedUser(
            email="restricted@example.com",
            password="password123",
        )
        # Test age restriction - call internal hook directly to test custom logic
        restricted_user.age = 25
        with restricted_user.bypass_perms():
            # No restriction for adults
            assert restricted_user._can_write(None) is True

        # Test age restriction for minors
        restricted_user.age = 16
        with restricted_user.bypass_perms():
            # Restriction applies for minors
            assert restricted_user._can_write(None) is False

        # Test with no age - should work
        restricted_user.age = None
        with restricted_user.bypass_perms():
            # No restriction when age is None
            assert restricted_user._can_write(None) is True

        # Test public API with bypass - bypass takes precedence over age restriction
        restricted_user.age = 16
        with restricted_user.bypass_perms():
            # Public API respects bypass_perms flag
            assert restricted_user.can_write() is True

    def test_register_user_class_with_jwt_fallback(self, unit_app) -> None:
        """Test that register_user_class works with JWT fallback."""

        class MyUserJWT(User):
            """Custom user class for JWT test."""

        # Register the user class
        register_user_class(MyUserJWT)

        # Create a test user
        with unit_app.app_context():
            with MyUserJWT.bypass_perms():
                user = MyUserJWT(email="test@example.com", password="password123")
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        # Verify JWT loader uses MyUser by testing get_current_user
        with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            current = MyUserJWT.get_current_user()
            assert current is not None
            assert isinstance(current, MyUserJWT)
            assert current.email == "test@example.com"

    def test_user_class_get_current_user_method(self, unit_app) -> None:
        """Test that User.get_current_user() returns typed user."""

        class MyUserClassMethod(User):
            """Custom user class for class method test."""

        # Register the user class
        register_user_class(MyUserClassMethod)

        # Create a test user
        with unit_app.app_context():
            with MyUserClassMethod.bypass_perms():
                user = MyUserClassMethod(email="test@example.com", password="password123")
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        # Test the classmethod
        with unit_app.test_client():
            with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                # This should return MyUserClassMethod | None
                current = MyUserClassMethod.get_current_user()
                assert current is not None
                assert isinstance(current, MyUserClassMethod)

    def test_user_extension_has_role_inheritance(self, unit_app) -> None:
        """Test that custom User subclass inherits has_role correctly."""

        class MyUserRoleInheritance(User):
            """Custom user class for role inheritance test."""

        # Register the user class
        register_user_class(MyUserRoleInheritance)

        # Create test users with roles
        with unit_app.app_context():
            with MyUserRoleInheritance.bypass_perms():
                admin_user = MyUserRoleInheritance(email="admin@example.com", password="password123")
                admin_user.save()
                admin_user.roles.append(UserRole(user=admin_user, role=DefaultUserRole.ADMIN))

                superadmin_user = MyUserRoleInheritance(email="super@example.com", password="password123")
                superadmin_user.save()
                superadmin_user.roles.append(UserRole(user=superadmin_user, role=DefaultUserRole.SUPERADMIN))

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(admin_user.id))

        with unit_app.test_client():
            with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                # Test is_admin
                assert is_current_user_admin() is True
                assert is_current_user_superadmin() is False

    def test_typed_get_current_user_with_custom_class(self, unit_app) -> None:
        """Test that MyUserTyped.get_current_user() is correctly typed."""

        class MyUserTyped(User):
            """Custom user class with extra field."""

            employee_id = "EMP001"

        # Register the user class
        register_user_class(MyUserTyped)

        # Create a test user
        with unit_app.app_context():
            with MyUserTyped.bypass_perms():
                user = MyUserTyped(email="test@example.com", password="password123")
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        with unit_app.test_client():
            with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                # Class method should return MyUserTyped
                typed_user = MyUserTyped.get_current_user()
                assert typed_user is not None
                assert isinstance(typed_user, MyUserTyped)
                # Custom field should be accessible
                assert typed_user.employee_id == "EMP001"
