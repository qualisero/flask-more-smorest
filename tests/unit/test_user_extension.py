"""Unit tests for extending defaults_module.DefaultUser model with custom columns/perms."""

import contextlib
import sys
import uuid
from collections.abc import Generator

import pytest
import sqlalchemy as sa
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import db, init_db, init_jwt
from flask_more_smorest.perms import (
    clear_registration,
    init_fms,
    is_current_user_admin,
    is_current_user_superadmin,
)
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.models.abstract_user import AbstractUser


def build_models() -> type[AbstractUser]:
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    import sys
    import types

    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomUser(AbstractUser):  # type: ignore[misc]
        __module__ = module_name
        __allow_unmapped__ = True

        custom_user_field: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)

    return CustomUser


@pytest.fixture(autouse=True)
def _reset_models(unit_app: Flask) -> Generator[None, None, None]:
    clear_registration()
    db.metadata.clear()
    with contextlib.suppress(Exception):
        sa.orm.clear_mappers()
    modules_to_unload = [
        "flask_more_smorest.perms.models.role",
        "flask_more_smorest.perms.models.token",
        "flask_more_smorest.perms.models.setting",
        "flask_more_smorest.perms.models.defaults",
        "flask_more_smorest.perms.models.user",
        "flask_more_smorest.perms.user_schemas",
    ]
    for module_name in modules_to_unload:
        sys.modules.pop(module_name, None)
    yield
    clear_registration()


@pytest.fixture
def unit_app() -> Generator[Flask, None, None]:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key"

    init_db(app)
    init_jwt(app)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def db_session(unit_app: Flask) -> Generator[None, None, None]:
    with unit_app.app_context():
        yield
        db.session.remove()
        db.drop_all()


@pytest.mark.usefixtures("reset_user_context")
class TestUserExtension:
    """Test extending defaults_module.DefaultUser model with custom columns and perms."""

    def test_user_extension_with_custom_columns(self, unit_app) -> None:
        """Test that custom defaults_module.DefaultUser subclass with extra columns works."""

        CustomUser = build_models()

        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

            user = CustomUser(
                email="custom@example.com",
                password="password123",
            )
        assert user.custom_user_field is None

    def test_user_extension_with_custom_permissions(self, unit_app) -> None:
        """Test that custom defaults_module.DefaultUser subclass with overridden permissions works."""

        CustomUser = build_models()

        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

            restricted_user = CustomUser(
                email="restricted@example.com",
                password="password123",
            )
        # Default AbstractUser write checks deny unauthenticated writes
        with restricted_user.bypass_perms():
            assert restricted_user._can_write(None) is False

        # Bypass perms should allow writes
        with restricted_user.bypass_perms():
            assert restricted_user.can_write() is True

    def test_init_fms_with_jwt_fallback(self, unit_app) -> None:
        """Test that init_fms works with JWT fallback."""

        CustomUser = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

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
        """Test that defaults_module.DefaultUser.get_current_user() returns typed user."""

        CustomUser = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

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
        """Test that custom defaults_module.DefaultUser subclass inherits has_role correctly."""

        CustomUser = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

            # Create test users with roles
            with CustomUser.bypass_perms():
                admin_user = CustomUser(email="admin@example.com", password="password123")
                admin_user.save()
                admin_user.roles.append(
                    defaults_module.DefaultUserRole(user=admin_user, role=defaults_module.BaseRoleEnum.ADMIN)
                )

                superadmin_user = CustomUser(email="super@example.com", password="password123")
                superadmin_user.save()
                superadmin_user.roles.append(
                    defaults_module.DefaultUserRole(user=superadmin_user, role=defaults_module.BaseRoleEnum.SUPERADMIN)
                )

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

        CustomUser = build_models()

        # Register the user class
        with unit_app.app_context():
            clear_registration()
            init_fms(user=CustomUser)
            db.drop_all()
            db.create_all()

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
