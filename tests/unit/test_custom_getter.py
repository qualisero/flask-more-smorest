"""Unit tests for extending DefaultUser model with custom current user getter."""

import uuid
from collections.abc import Generator

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import db
from flask_more_smorest.perms import (
    clear_registration,
    init_fms,
    is_current_user_admin,
    is_current_user_superadmin,
)
from flask_more_smorest.perms.models.abstract_role import AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.perms.models.defaults import (
    DefaultDomain,
    DefaultToken,
    DefaultUser,
    DefaultUserRole,
    DefaultUserSetting,
)


def build_models() -> (
    tuple[
        type[AbstractUser],
        type[AbstractUserRole],
        type[AbstractToken],
        type[AbstractUserSetting],
    ]
):
    suffix = uuid.uuid4().hex
    user_table = f"custom_user_{suffix}"

    class CustomUser(AbstractUser):  # type: ignore[misc]
        __tablename__ = user_table
        __allow_unmapped__ = True

        id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
        email: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)
        password: Mapped[bytes | None] = mapped_column(sa.LargeBinary(128), nullable=True)
        is_enabled: Mapped[bool] = mapped_column(sa.Boolean(), default=True)

    class CustomUserRole(AbstractUserRole):
        __tablename__ = f"custom_user_role_{suffix}"

        user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            db.ForeignKey(f"{user_table}.id"),
            nullable=False,
        )
        domain_id: Mapped[uuid.UUID | None] = mapped_column(
            sa.Uuid(as_uuid=True),
            db.ForeignKey("domain.id"),
            nullable=True,
            default=None,
        )
        _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

    class CustomToken(AbstractToken):
        __tablename__ = f"custom_token_{suffix}"

        can_renew: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)

    class CustomUserSetting(AbstractUserSetting):
        __tablename__ = f"custom_user_setting_{suffix}"

        category: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    return CustomUser, CustomUserRole, CustomToken, CustomUserSetting  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def _clear_registration() -> Generator[None, None, None]:
    clear_registration()
    yield
    clear_registration()
    init_fms(
        user=DefaultUser,
        role=DefaultUserRole,
        token=DefaultToken,
        domain=DefaultDomain,
        setting=DefaultUserSetting,
    )


class TestCustomGetter:
    """Test extending DefaultUser model with custom get_current_user mechanism."""

    def test_init_fms_with_custom_getter(self, unit_app, db_session) -> None:
        """Test that init_fms with custom getter works."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        clear_registration()
        init_fms(
            user=CustomUser,
            role=CustomUserRole,
            token=CustomToken,
            domain=DefaultDomain,
            setting=CustomUserSetting,
        )

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

    def test_custom_getter_overrides_jwt_fallback(self, unit_app, db_session) -> None:
        """Test that custom getter takes precedence over JWT."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        clear_registration()
        init_fms(
            user=CustomUser,
            role=CustomUserRole,
            token=CustomToken,
            domain=DefaultDomain,
            setting=CustomUserSetting,
        )

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

    def test_custom_getter_returns_none(self, unit_app, db_session) -> None:
        """Test that custom getter returning None is handled correctly."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        clear_registration()
        init_fms(
            user=CustomUser,
            role=CustomUserRole,
            token=CustomToken,
            domain=DefaultDomain,
            setting=CustomUserSetting,
        )

        # Custom getter returns None
        def unauthenticated_get_user() -> CustomUser | None:  # type: ignore[valid-type]
            return None

        init_fms(get_current_user=unauthenticated_get_user)

        # Should return None when no user authenticated
        current = CustomUser.get_current_user()
        assert current is None

    def test_multiple_user_classes(self, unit_app, db_session) -> None:
        """Test that multiple user classes can coexist with different getters."""

        CustomUser1, CustomUserRole1, CustomToken1, CustomUserSetting1 = build_models()
        CustomUser2, CustomUserRole2, CustomToken2, CustomUserSetting2 = build_models()

        clear_registration()
        init_fms(
            user=CustomUser1,
            role=CustomUserRole1,
            token=CustomToken1,
            domain=DefaultDomain,
            setting=CustomUserSetting1,
        )

        # Create test users
        with CustomUser1.bypass_perms():
            employee = CustomUser1(email="employee@example.com", password="password123")
            employee.employee_id = "EMP001"  # type: ignore[attr-defined]
            employee.save()

        with CustomUser2.bypass_perms():
            customer = CustomUser2(email="customer@example.com", password="password123")
            customer.customer_id = "CUST001"  # type: ignore[attr-defined]
            customer.save()

        # Custom getter returns employee
        def get_employee() -> CustomUser1 | None:  # type: ignore[valid-type]
            return db.session.query(CustomUser1).filter_by(email="employee@example.com").first()

        init_fms(get_current_user=get_employee)

        # Should return employee
        employee_current = CustomUser1.get_current_user()
        assert employee_current is not None
        assert isinstance(employee_current, CustomUser1)
        assert employee_current.employee_id == "EMP001"  # type: ignore[attr-defined]

        # Custom getter returns customer
        def get_customer() -> CustomUser2 | None:  # type: ignore[valid-type]
            return db.session.query(CustomUser2).filter_by(email="customer@example.com").first()

        init_fms(get_current_user=get_customer)

        customer_current = CustomUser2.get_current_user()
        assert customer_current is not None
        assert isinstance(customer_current, CustomUser2)
        assert customer_current.customer_id == "CUST001"  # type: ignore[attr-defined]

    def test_custom_getter_with_roles(self, unit_app, db_session) -> None:
        """Test custom getter with role checks."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        clear_registration()
        init_fms(
            user=CustomUser,
            role=CustomUserRole,
            token=CustomToken,
            domain=DefaultDomain,
            setting=CustomUserSetting,
        )

        # Create test user with admin role
        with CustomUser.bypass_perms():
            user = CustomUser(email="admin@example.com", password="password123")
            user.save()
            user.roles.append(CustomUserRole(user=user, role="ADMIN"))

        # Custom getter returns admin user
        def get_admin() -> CustomUser | None:  # type: ignore[valid-type]
            return db.session.query(CustomUser).filter_by(email="admin@example.com").first()

        init_fms(get_current_user=get_admin)

        # Test role checks
        assert is_current_user_admin() is True
        assert is_current_user_superadmin() is False
