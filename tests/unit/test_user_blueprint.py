"""Unit tests for UserBlueprint class."""

# pyright: reportAttributeAccessIssue=false

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
from flask_more_smorest.perms.models.abstract_role import AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.perms.models.defaults import (
    DefaultDomain,
    DefaultUser,
)

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


def build_models() -> (
    tuple[
        type[AbstractUser],
        type[AbstractUserRole],
        type[AbstractToken],
        type[AbstractUserSetting],
    ]
):
    suffix = uuid.uuid4().hex
    user_table = f"blueprint_user_{suffix}"

    class CustomUser(AbstractUser):  # type: ignore[misc]
        __tablename__ = user_table
        __allow_unmapped__ = True

        id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
        email: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)
        password: Mapped[bytes | None] = mapped_column(sa.LargeBinary(128), nullable=True)
        is_enabled: Mapped[bool] = mapped_column(sa.Boolean(), default=True)

    class CustomUserRole(AbstractUserRole):
        __tablename__ = f"blueprint_user_role_{suffix}"

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
        __tablename__ = f"blueprint_token_{suffix}"

        pass

    class CustomUserSetting(AbstractUserSetting):
        __tablename__ = f"blueprint_user_setting_{suffix}"

        user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            db.ForeignKey(f"{user_table}.id"),
            nullable=False,
        )
        key: Mapped[str] = mapped_column(sa.String(80), nullable=False)
        value: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)

    return CustomUser, CustomUserRole, CustomToken, CustomUserSetting  # type: ignore[return-value]


class TestUserBlueprintClass:
    """Tests for UserBlueprint class."""

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

    def test_user_blueprint_has_crud_endpoints(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test UserBlueprint registers standard CRUD endpoints."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check that CRUD routes are registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]

            # Standard CRUD routes
            assert "/api/users/" in rules  # INDEX and POST
            assert "/api/users/<uuid:users_id>" in rules  # GET, PATCH, DELETE

    def test_user_blueprint_has_login_endpoint(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test UserBlueprint registers login endpoint."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check login route is registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/users/login/" in rules

    def test_user_blueprint_has_me_endpoint(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test UserBlueprint registers current user profile endpoint."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Check /me route is registered
        with unit_app.app_context():
            rules = [rule.rule for rule in unit_app.url_map.iter_rules()]
            assert "/api/users/me/" in rules

    def test_user_blueprint_login_endpoint_works(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test login endpoint returns JWT token."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a test user
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="test@example.com", password="password123")
            user.save()

        # Login
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data

    def test_user_blueprint_login_fails_with_wrong_password(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test login fails with wrong password."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a test user
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="test@example.com", password="password123")
            user.save()

        # Login with wrong password
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    def test_user_blueprint_login_fails_for_disabled_user(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test login fails for disabled user."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a disabled test user
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="test@example.com", password="password123")
            user.is_enabled = False
            user.save()

        # Login with disabled user
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 401

    def test_user_blueprint_me_endpoint_requires_auth(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test /me endpoint requires authentication."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Request without auth header
        response = client.get("/api/users/me/")
        assert response.status_code == 401

    def test_user_blueprint_me_endpoint_returns_current_user(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test /me endpoint returns current user data."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a test user
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="test@example.com", password="password123")
            user.save()
            user_id = user.id

        # Login to get token
        login_response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )
        token = login_response.get_json()["access_token"]

        # Access /me endpoint with auth token
        response = client.get(
            "/api/users/me/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == str(user_id)
        assert data["email"] == "test@example.com"

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
    """Test UserBlueprint with custom DefaultUser model."""

    def test_user_blueprint_with_custom_user_class(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test UserBlueprint works with custom DefaultUser model."""

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

        # Create blueprint with public registration user
        bp = UserBlueprint(model=CustomUser, schema=CustomUser.Schema)
        api.register_blueprint(bp)

        # Verify POST method config has public=True
        post_config = bp._config.methods.get(CRUDMethod.POST, {})
        assert post_config.get("public") is True, "POST should be marked as public when PUBLIC_REGISTRATION=True"

    def test_public_registration_allows_unauthenticated_user_creation(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that PUBLIC_REGISTRATION=True allows creating users without authentication."""

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

            # Recreate tables to include CustomUser
            db.drop_all()
            db.create_all()

        # Create blueprint with public registration user
        bp = UserBlueprint(model=CustomUser, schema=CustomUser.Schema)
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Try to create a user without authentication - should succeed
        response = client.post(
            "/api/users/",
            json={"email": "newuser@example.com", "password": "password123"},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.get_json()}"
        data = response.get_json()
        assert data["email"] == "newuser@example.com"

    def test_no_public_registration_requires_auth_for_post(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that without PUBLIC_REGISTRATION, POST requires authentication."""
        from flask_more_smorest.crud.crud_blueprint import CRUDMethod

        # Default DefaultUser has PUBLIC_REGISTRATION=False
        bp = UserBlueprint()
        api.register_blueprint(bp)

        # Verify POST method config does NOT have public=True
        post_config = bp._config.methods.get(CRUDMethod.POST, {})
        assert post_config.get("public") is not True, "POST should NOT be public by default"

        client = unit_app.test_client()

        # Try to create a user without authentication - should fail with 401
        response = client.post(
            "/api/users/",
            json={"email": "newuser@example.com", "password": "password123"},
        )

        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestUserBlueprintIntegration:
    """Integration tests for UserBlueprint with full app setup."""

    def test_complete_user_registration_and_login_flow(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test complete user flow: create -> login -> access profile -> update."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Step 1: Create a new user (bypassing perms for test)
        with DefaultUser.bypass_perms():
            user = DefaultUser(email="newuser@example.com", password="securepass123")
            user.save()
            user_id = user.id

        # Step 2: Login with the new user
        login_response = client.post(
            "/api/users/login/",
            json={"email": "newuser@example.com", "password": "securepass123"},
        )
        assert login_response.status_code == 200
        token_data = login_response.get_json()
        token = token_data["access_token"]

        # Step 3: Access profile using /me endpoint
        profile_response = client.get(
            "/api/users/me/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.get_json()
        assert profile_data["email"] == "newuser@example.com"
        assert profile_data["id"] == str(user_id)

    def test_multiple_user_blueprint_instances(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
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


class TestCustomUserInheritedColumns:
    """Tests for custom user inherited columns."""

    def test_custom_user_instance_has_all_inherited_columns(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that DefaultUser instances have all expected column values."""

        # Create a DefaultUser instance
        with DefaultUser.bypass_perms():
            user = DefaultUser(
                email="testuser@example.com",
                password="password123",
            )
            user.save()

        # Ensure inherited columns exist and have correct values
        assert user.id is not None
        assert user.email == "testuser@example.com"
        assert user.is_enabled is True
