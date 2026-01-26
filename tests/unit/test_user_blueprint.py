"""Unit tests for UserBlueprint class.

This file contains only true unit tests that test class initialization,
configuration, and endpoint registration without requiring full
integration testing with database operations.

Integration tests for actual endpoint behavior are in:
- tests/integration/test_user_defaults.py
"""

# pyright: reportAttributeAccessIssue=false

import contextlib
import sys
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import Api, UserBlueprint, db
from flask_more_smorest.crud.crud_blueprint import CRUDMethod
from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.models.abstract_user import AbstractUser

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


@pytest.fixture
def db_session(unit_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with unit_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


# Fixture alias for backward compatibility with test signatures
@pytest.fixture
def api(unit_api: "Api") -> "Api":
    """Alias for unit_api to match test method signatures."""
    return unit_api


def build_models() -> type[AbstractUser]:
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    import sys
    import types

    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomUser(AbstractUser):
        __module__ = module_name
        __allow_unmapped__ = True
        PUBLIC_REGISTRATION = True

        some_custom_field: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)

    return CustomUser


def reset_models() -> None:
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


class TestUserBlueprintClass:
    """Tests for UserBlueprint class - CLASS INITIALIZATION AND CONFIGURATION."""

    def test_user_blueprint_instantiation_with_defaults(self, unit_app: Flask, api: Api) -> None:
        """Test UserBlueprint can be instantiated with default parameters."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        assert bp.name == "users"
        assert bp.url_prefix == "/api/users/"

    def test_user_blueprint_custom_configuration(self, unit_app: Flask, api: Api) -> None:
        """Test UserBlueprint can be instantiated with custom parameters."""
        bp = UserBlueprint(
            name="custom_users",
            url_prefix="/api/v2/users/",
            skip_methods=[CRUDMethod.DELETE],
        )
        api.register_blueprint(bp)

        assert bp.name == "custom_users"
        assert bp.url_prefix == "/api/v2/users/"

    def test_user_blueprint_has_crud_endpoints(self, unit_app: Flask, api: Api) -> None:
        """Test UserBlueprint registers standard CRUD endpoints."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check that CRUD routes are registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]

            # Standard CRUD routes
            assert "/api/users/" in rules  # INDEX and POST
            assert "/api/users/<uuid:users_id>" in rules  # GET, PATCH, DELETE

    def test_user_blueprint_has_login_endpoint(self, unit_app: Flask, api: Api) -> None:
        """Test UserBlueprint registers login endpoint."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check login route is registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/users/login/" in rules

    def test_user_blueprint_has_me_endpoint(self, unit_app: Flask, api: Api) -> None:
        """Test UserBlueprint registers current user profile endpoint."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check /me route is registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/users/me/" in rules

    def test_user_blueprint_skip_methods(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test UserBlueprint skip_methods configuration."""
        bp = UserBlueprint(skip_methods=[CRUDMethod.DELETE, CRUDMethod.PATCH])
        api.register_blueprint(bp)

        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/users/<uuid:users_id>" in rules

            # Ensure delete and patch are not registered
            delete_routes = [
                rule for rule in unit_app.url_map.iter_rules() if rule.methods is not None and "DELETE" in rule.methods
            ]
            patch_routes = [
                rule for rule in unit_app.url_map.iter_rules() if rule.methods is not None and "PATCH" in rule.methods
            ]
            assert len(delete_routes) == 0
            assert len(patch_routes) == 0

    def test_user_blueprint_inherits_from_crud_blueprint(self) -> None:
        """Test that UserBlueprint inherits from PermsBlueprint (CRUDBlueprint with mixins)."""
        from flask_more_smorest.perms import PermsBlueprint

        assert issubclass(UserBlueprint, PermsBlueprint)

    def test_user_blueprint_has_permission_decorators(self, unit_app: Flask, api: Api) -> None:
        """Test that UserBlueprint has permission-related decorators."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check that UserBlueprint has permission decorators
        assert hasattr(bp, "public_endpoint")
        assert callable(bp.public_endpoint)


class TestUserBlueprintWithCustomUser:
    """Test UserBlueprint with custom User model - CONFIGURATION TESTS."""

    @pytest.fixture(autouse=True)
    def _restore_defaults(self, unit_app: Flask) -> Iterator[None]:
        with unit_app.app_context():
            reset_models()
            init_fms(
                user=defaults_module.User,
                role=defaults_module.UserRole,
                token=defaults_module.Token,
                domain=defaults_module.Domain,
                setting=defaults_module.UserSetting,
            )
            db.create_all()
        yield
        with unit_app.app_context():
            reset_models()
            init_fms(
                user=defaults_module.User,
                role=defaults_module.UserRole,
                token=defaults_module.Token,
                domain=defaults_module.Domain,
                setting=defaults_module.UserSetting,
            )
            db.create_all()

    def test_user_blueprint_with_custom_user_class(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test UserBlueprint works with custom User model."""

        reset_models()
        CustomUser = build_models()

        with unit_app.app_context():
            init_fms(user=CustomUser)

        # Create blueprint with custom user model
        bp = UserBlueprint(model=CustomUser, schema=CustomUser.Schema)
        api.register_blueprint(bp)

        # Verify the blueprint uses the custom model
        assert bp._config.model_cls == CustomUser

        # Verify PUBLIC_REGISTRATION flag is set
        assert CustomUser.PUBLIC_REGISTRATION is True

    def test_public_registration_makes_post_endpoint_public(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that PUBLIC_REGISTRATION=True makes POST endpoint public."""
        from flask_more_smorest.crud.crud_blueprint import CRUDMethod

        reset_models()
        CustomUser = build_models()

        with unit_app.app_context():
            init_fms(user=CustomUser)

        # Create blueprint with public registration user
        bp = UserBlueprint(model=CustomUser, schema=CustomUser.Schema)
        api.register_blueprint(bp)

        # Verify POST method config has public=True
        post_config = bp._config.methods.get(CRUDMethod.POST, {})
        assert post_config.get("public") is True, "POST should be marked as public when PUBLIC_REGISTRATION=True"

    def test_no_public_registration_requires_auth_for_post(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that without PUBLIC_REGISTRATION, POST requires authentication."""
        from flask_more_smorest.crud.crud_blueprint import CRUDMethod

        # Default User has PUBLIC_REGISTRATION=False
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Verify POST method config does NOT have public=True
        post_config = bp._config.methods.get(CRUDMethod.POST, {})
        assert post_config.get("public") is not True, "POST should NOT be public by default"


class TestUserBlueprintMultipleInstances:
    """Tests for multiple UserBlueprint instances."""

    def test_multiple_user_blueprint_instances(self, unit_app: Flask, api: Api) -> None:
        """Test that multiple UserBlueprint instances can coexist with different configs."""

        # Create two UserBlueprints with different prefixes
        bp1 = UserBlueprint(name="users_v1", url_prefix="/api/v1/users/")
        bp2 = UserBlueprint(name="users_v2", url_prefix="/api/v2/users/")

        api.register_blueprint(bp1)
        api.register_blueprint(bp2)

        # Check that both blueprints are registered
        assert bp1.name == "users_v1"
        assert bp2.name == "users_v2"

        # Check that routes from both blueprints exist
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/v1/users/" in rules
            assert "/api/v2/users/" in rules
