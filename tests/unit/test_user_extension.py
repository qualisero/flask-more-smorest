"""Unit tests for extending DefaultUser model with custom columns/perms."""

import uuid
from collections.abc import Generator

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

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
    BaseRoleEnum,
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
    user_table = f"user_ext_{suffix}"

    class CustomUser(AbstractUser):  # type: ignore[misc]
        __tablename__ = user_table
        __allow_unmapped__ = True

        id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
        email: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)
        password: Mapped[bytes | None] = mapped_column(sa.LargeBinary(128), nullable=True)
        is_enabled: Mapped[bool] = mapped_column(sa.Boolean(), default=True)

    class CustomUserRole(AbstractUserRole):
        __tablename__ = f"user_ext_role_{suffix}"

        user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{user_table}.id"),
            nullable=False,
        )
        domain_id: Mapped[uuid.UUID | None] = mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("domain.id"),
            nullable=True,
            default=None,
        )
        _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

    class CustomToken(AbstractToken):
        __tablename__ = f"user_ext_token_{suffix}"

        user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{user_table}.id"),
            nullable=False,
        )
        token: Mapped[str] = mapped_column(sa.String(1024), nullable=False)

    class CustomUserSetting(AbstractUserSetting):
        __tablename__ = f"user_ext_setting_{suffix}"

        user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{user_table}.id"),
            nullable=False,
        )
        key: Mapped[str] = mapped_column(sa.String(80), nullable=False)
        value: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)

    return CustomUser, CustomUserRole, CustomToken, CustomUserSetting  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def _clear_registration_after_test() -> Generator[None, None, None]:
    yield
    clear_registration()
    init_fms(
        user=DefaultUser,
        role=DefaultUserRole,
        token=DefaultToken,
        domain=DefaultDomain,
        setting=DefaultUserSetting,
    )


@pytest.mark.usefixtures("reset_user_context")
class TestUserExtension:
    """Test extending DefaultUser model with custom columns and perms."""

    def test_user_extension_with_custom_columns(self, unit_app) -> None:
        """Test that custom DefaultUser subclass with extra columns works."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            user = CustomUser(
                email="custom@example.com",
                password="password123",
            )
        assert user.employee_id == "EMP001"  # type: ignore[attr-defined]
        assert user.department == "Engineering"  # type: ignore[attr-defined]
        assert user.salary == 100000  # type: ignore[attr-defined]

    def test_user_extension_with_custom_permissions(self, unit_app) -> None:
        """Test that custom DefaultUser subclass with overridden permissions works."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            restricted_user = CustomUser(
                email="restricted@example.com",
                password="password123",
            )
        # Test age restriction - call internal hook directly to test custom logic
        restricted_user.age = 25  # type: ignore[attr-defined]
        with restricted_user.bypass_perms():
            # No restriction for adults
            assert restricted_user._can_write(None) is True

        # Test age restriction for minors
        restricted_user.age = 16  # type: ignore[attr-defined]
        with restricted_user.bypass_perms():
            # Restriction applies for minors
            assert restricted_user._can_write(None) is False

        # Test with no age - should work
        restricted_user.age = None  # type: ignore[attr-defined]
        with restricted_user.bypass_perms():
            # No restriction when age is None
            assert restricted_user._can_write(None) is True

        # Test public API with bypass - bypass takes precedence over age restriction
        restricted_user.age = 16  # type: ignore[attr-defined]
        with restricted_user.bypass_perms():
            # Public API respects bypass_perms flag
            assert restricted_user.can_write() is True

    def test_init_fms_with_jwt_fallback(self, unit_app) -> None:
        """Test that init_fms works with JWT fallback."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            # Create a test user
            with CustomUser.bypass_perms():
                user = CustomUser(email="test@example.com", password="password123")
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        # Verify JWT loader uses MyUser by testing get_current_user
        with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            current = CustomUser.get_current_user()
            assert current is not None
            assert isinstance(current, CustomUser)
            assert current.email == "test@example.com"

    def test_user_class_get_current_user_method(self, unit_app) -> None:
        """Test that DefaultUser.get_current_user() returns typed user."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            # Create a test user
            with CustomUser.bypass_perms():
                user = CustomUser(email="test@example.com", password="password123")
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        # Test the classmethod
        with unit_app.test_client():
            with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                # This should return CustomUser | None
                current = CustomUser.get_current_user()
                assert current is not None
                assert isinstance(current, CustomUser)

    def test_user_extension_has_role_inheritance(self, unit_app) -> None:
        """Test that custom DefaultUser subclass inherits has_role correctly."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            # Create test users with roles
            with CustomUser.bypass_perms():
                admin_user = CustomUser(email="admin@example.com", password="password123")
                admin_user.save()
                admin_user.roles.append(CustomUserRole(user=admin_user, role=BaseRoleEnum.ADMIN))

                superadmin_user = CustomUser(email="super@example.com", password="password123")
                superadmin_user.save()
                superadmin_user.roles.append(CustomUserRole(user=superadmin_user, role=BaseRoleEnum.SUPERADMIN))

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(admin_user.id))

        with unit_app.test_client():
            with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
                # Test is_admin
                assert is_current_user_admin() is True
                assert is_current_user_superadmin() is False

    def test_typed_get_current_user_with_custom_class(self, unit_app) -> None:
        """Test that CustomUser.get_current_user() is correctly typed."""

        CustomUser, CustomUserRole, CustomToken, CustomUserSetting = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(
                user=CustomUser,
                role=CustomUserRole,
                token=CustomToken,
                domain=DefaultDomain,
                setting=CustomUserSetting,
            )

            # Create a test user
            with CustomUser.bypass_perms():
                user = CustomUser(email="test@example.com", password="password123")
                user.employee_id = "EMP001"  # type: ignore[attr-defined]
                user.save()

            # Create JWT token
            from flask_jwt_extended import create_access_token

            token = create_access_token(identity=str(user.id))

        # Test the classmethod
        with unit_app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            current = CustomUser.get_current_user()
            assert current is not None
            assert isinstance(current, CustomUser)
