"""Unit tests for extending User model with custom current user getter."""

from flask_more_smorest import db
from flask_more_smorest.perms import (
    User,
    get_current_user,
    is_current_user_admin,
    is_current_user_superadmin,
    register_user_class,
)


class TestCustomGetter:
    """Test extending User model with custom get_current_user mechanism."""

    def test_register_user_class_with_custom_getter(self, unit_app, db_session) -> None:
        """Test that register_user_class with custom getter works."""

        class ExternalUser(User):
            """Custom user class."""

            external_id = "EXT123"
            source_system = "LDAP"

        # Create a test user in database
        with ExternalUser.bypass_perms():
            user = ExternalUser(
                email="external@example.com",
                password="password123",
                external_id="EXT123",
            )
            user.save()

        # Mock external authentication
        def external_get_user() -> ExternalUser | None:
            """Simulate external auth (LDAP, OAuth, etc.)."""
            # In real scenario, this would call external service
            # For testing, we'll just return our created user
            return db.session.query(ExternalUser).filter_by(email="external@example.com").first()

        # Register user class with custom getter
        register_user_class(ExternalUser, get_current_user=external_get_user)

        # Custom getter should be used
        current = ExternalUser.get_current_user()
        assert current is not None
        assert isinstance(current, ExternalUser)
        assert current.external_id == "EXT123"
        assert current.source_system == "LDAP"

    def test_custom_getter_overrides_jwt_fallback(self, unit_app, db_session) -> None:
        """Test that custom getter takes precedence over JWT."""

        class MyUserOverride(User):
            """Custom user class for override test."""

            __tablename__ = "user_override"

        # Create test users
        with MyUserOverride.bypass_perms():
            jwt_user = MyUserOverride(email="jwt@example.com", password="password123")
            jwt_user.save()

            custom_user = MyUserOverride(email="custom@example.com", password="password123")
            custom_user.save()

        # Register custom getter that always returns custom_user
        def custom_get_user() -> MyUserOverride | None:
            return db.session.query(MyUserOverride).filter_by(email="custom@example.com").first()

        register_user_class(MyUserOverride, get_current_user=custom_get_user)

        # Custom getter should override JWT
        current = get_current_user(MyUserOverride)
        assert current is not None
        assert current.email == "custom@example.com"

    def test_custom_getter_returns_none(self, unit_app, db_session) -> None:
        """Test that custom getter returning None is handled correctly."""

        class MyUserNone(User):
            """Custom user class for None test."""

            __tablename__ = "user_none"

        def unauthenticated_get_user() -> MyUserNone | None:
            return None

        register_user_class(MyUserNone, get_current_user=unauthenticated_get_user)

        # Should return None
        current = get_current_user(MyUserNone)
        assert current is None

        # Admin checks should return False
        assert is_current_user_admin() is False
        assert is_current_user_superadmin() is False

    def test_multiple_user_classes(self, unit_app, db_session) -> None:
        """Test handling multiple user classes (advanced use case)."""

        class TestEmployeeUser(User):
            """Employee user for testing."""

            employee_type = "EMPLOYEE"

        class TestContractorUser(User):
            """Contractor user for testing."""

            contractor_type = "CONTRACTOR"

        # Create users
        with TestEmployeeUser.bypass_perms():
            employee = TestEmployeeUser(email="employee@example.com", password="password123")
            employee.save()

            contractor = TestContractorUser(email="contractor@example.com", password="password123")
            contractor.save()

        # Register TestEmployeeUser with its getter
        def get_employee() -> TestEmployeeUser | None:
            return db.session.query(TestEmployeeUser).first()

        register_user_class(TestEmployeeUser, get_current_user=get_employee)

        # Typed get should return TestEmployeeUser
        current = get_current_user(TestEmployeeUser)
        assert current is not None
        assert isinstance(current, TestEmployeeUser)
        assert current.employee_type == "EMPLOYEE"

    def test_custom_getter_with_roles(self, unit_app, db_session) -> None:
        """Test that custom getter works with role-based permissions."""

        class MyUserRole(User):
            """Custom user class for roles test."""

            __tablename__ = "user_roles"

            def _can_write(self, current_user) -> bool:
                """Custom write permission.

                Args:
                    current_user: The current authenticated user, or None
                """
                if current_user is None:
                    return False
                try:
                    # Only superadmins can write
                    return current_user.is_superadmin
                except Exception:
                    return False

        # Create test users with roles
        with MyUserRole.bypass_perms():
            from flask_more_smorest.perms.models import DefaultUserRole, UserRole

            admin_user = MyUserRole(email="admin@example.com", password="password123")
            admin_user.save()
            admin_user.roles.append(UserRole(user=admin_user, role=DefaultUserRole.ADMIN))

            regular_user = MyUserRole(email="regular@example.com", password="password123")
            regular_user.save()

        # Custom getter returns admin_user
        def get_admin() -> MyUserRole | None:
            return db.session.query(MyUserRole).filter_by(email="admin@example.com").first()

        register_user_class(MyUserRole, get_current_user=get_admin)

        # Admin checks should work
        assert is_current_user_admin() is True
        assert is_current_user_superadmin() is False
