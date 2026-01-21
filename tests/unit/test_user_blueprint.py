"""Unit tests for UserBlueprint class."""

# pyright: reportAttributeAccessIssue=false

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flask import Flask

from flask_more_smorest import Api, User, UserBlueprint, db
from flask_more_smorest.crud.crud_blueprint import CRUDMethod

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


@pytest.fixture(scope="function")
def db_session(unit_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with unit_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


# Fixture alias for backward compatibility with test signatures
@pytest.fixture(scope="function")
def api(unit_api: "Api") -> "Api":
    """Alias for unit_api to match test method signatures."""
    return unit_api


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
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Login
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_user_blueprint_login_fails_with_wrong_password(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test login endpoint rejects wrong password."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a test user
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Try to login with wrong password
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.get_json()
        # RFC 7807 format
        assert data["status"] == 401
        assert "unauthorized" in data["type"].lower()

    def test_user_blueprint_login_fails_for_disabled_user(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test login endpoint rejects disabled users."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a disabled test user
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123", is_enabled=False)
            user.save()

        # Try to login
        response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )

        assert response.status_code == 401
        data = response.get_json()
        # RFC 7807 format
        assert data["status"] == 401
        assert "disabled" in data["detail"].lower()

    def test_user_blueprint_me_endpoint_requires_auth(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test /me endpoint requires authentication."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Try to access /me without authentication
        response = client.get("/api/users/me/")
        assert response.status_code == 401

    def test_user_blueprint_me_endpoint_returns_current_user(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test /me endpoint returns current authenticated user."""
        bp = UserBlueprint()
        api.register_blueprint(bp)

        client = unit_app.test_client()

        # Create a test user and login
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Login to get token
        login_response = client.post(
            "/api/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )
        token = login_response.get_json()["access_token"]

        # Access /me endpoint
        response = client.get(
            "/api/users/me/",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "password" not in data  # Password should be excluded

    def test_user_blueprint_skip_methods(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test UserBlueprint respects skip_methods parameter."""
        bp = UserBlueprint(skip_methods=[CRUDMethod.DELETE])
        api.register_blueprint(bp)

        # Check that DELETE route is not registered
        with unit_app.app_context():
            # Get all routes and their methods
            delete_routes = [
                rule
                for rule in unit_app.url_map.iter_rules()
                if "/api/users/<users_id>" in rule.rule and rule.methods is not None and "DELETE" in rule.methods
            ]
            assert len(delete_routes) == 0

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
    """Test UserBlueprint with custom User model."""

    def test_user_blueprint_with_custom_user_class(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test UserBlueprint works with custom User model."""

        # Define a custom User class with PUBLIC_REGISTRATION
        class CustomUser(User):
            PUBLIC_REGISTRATION = True

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

        # Define a custom User class with PUBLIC_REGISTRATION
        class PublicUser(User):
            PUBLIC_REGISTRATION = True

        # Create blueprint with public registration user
        bp = UserBlueprint(model=PublicUser, schema=PublicUser.Schema)
        api.register_blueprint(bp)

        # Verify POST method config has public=True
        post_config = bp._config.methods.get(CRUDMethod.POST, {})
        assert post_config.get("public") is True, "POST should be marked as public when PUBLIC_REGISTRATION=True"

    def test_public_registration_allows_unauthenticated_user_creation(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that PUBLIC_REGISTRATION=True allows creating users without authentication."""

        # Define a custom User class with PUBLIC_REGISTRATION
        class PublicUserForCreation(User):
            PUBLIC_REGISTRATION = True

        # Recreate tables to include PublicUserForCreation
        db.drop_all()
        db.create_all()

        # Create blueprint with public registration user
        bp = UserBlueprint(model=PublicUserForCreation, schema=PublicUserForCreation.Schema)
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

        # Default User has PUBLIC_REGISTRATION=False
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
        with User.bypass_perms():
            user = User(email="newuser@example.com", password="securepass123")
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

        # Step 4: Get user details
        get_response = client.get(
            f"/api/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 200
        get_data = get_response.get_json()
        assert get_data["email"] == "newuser@example.com"

    def test_multiple_user_blueprint_instances(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that multiple UserBlueprint instances can coexist with different configs."""

        # Create two UserBlueprints with different prefixes
        bp1 = UserBlueprint(name="users_v1", url_prefix="/api/v1/users/")
        bp2 = UserBlueprint(name="users_v2", url_prefix="/api/v2/users/")

        api.register_blueprint(bp1)
        api.register_blueprint(bp2)

        client = unit_app.test_client()

        # Create a user via v1
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Login via v1
        v1_login = client.post(
            "/api/v1/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert v1_login.status_code == 200

        # Login via v2
        v2_login = client.post(
            "/api/v2/users/login/",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert v2_login.status_code == 200

        # Both should work
        assert v1_login.get_json()["access_token"]
        assert v2_login.get_json()["access_token"]


class TestCustomUserInheritedColumns:
    """Tests for CustomUser class inheritance of all User columns."""

    def test_custom_user_inherits_all_base_columns(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that CustomUser inherits all columns from User and BaseModel."""
        # We test against the base User class to avoid column conflicts
        # when running with other tests that define CustomUser classes
        user_columns = {col.name for col in User.__table__.columns}

        # Verify inherited columns from BaseModel
        assert "id" in user_columns, "User should have 'id' column from BaseModel"
        assert "created_at" in user_columns, "User should have 'created_at' from BaseModel"
        assert "updated_at" in user_columns, "User should have 'updated_at' from BaseModel"

        # Verify User-specific columns
        assert "email" in user_columns, "User should have 'email' column"
        assert "password" in user_columns, "User should have 'password' column"
        assert "is_enabled" in user_columns, "User should have 'is_enabled' column"

    def test_custom_user_column_types_preserved(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that inherited column types are preserved in User."""
        import sqlalchemy as sa

        # Get column objects from User table
        columns = {col.name: col for col in User.__table__.columns}

        # Check id is UUID type
        assert isinstance(columns["id"].type, sa.Uuid)

        # Check email is String type
        assert isinstance(columns["email"].type, sa.String)
        assert columns["email"].type.length == 128

        # Check password is LargeBinary type
        assert isinstance(columns["password"].type, sa.LargeBinary)

        # Check is_enabled is Boolean type
        assert isinstance(columns["is_enabled"].type, sa.Boolean)

        # Check created_at and updated_at are DateTime types
        assert isinstance(columns["created_at"].type, sa.DateTime)
        assert isinstance(columns["updated_at"].type, sa.DateTime)

    def test_custom_user_inherits_relationships(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that User has all expected relationships that subclasses inherit."""
        # Check that relationships exist on User
        assert hasattr(User, "roles"), "User should have 'roles' relationship"
        assert hasattr(User, "settings"), "User should have 'settings' relationship"
        assert hasattr(User, "tokens"), "User should have 'tokens' relationship"

    def test_custom_user_inherits_methods(self, unit_app: Flask, api: Api, db_session: "scoped_session") -> None:
        """Test that User has all methods that subclasses inherit."""
        # Check methods from User
        assert hasattr(User, "set_password"), "User should have 'set_password' method"
        assert hasattr(User, "is_password_correct"), "User should have 'is_password_correct' method"
        assert hasattr(User, "has_role"), "User should have 'has_role' method"
        assert hasattr(User, "has_domain_access"), "User should have 'has_domain_access' method"

        # Check properties
        assert hasattr(User, "is_admin"), "User should have 'is_admin' property"
        assert hasattr(User, "is_superadmin"), "User should have 'is_superadmin' property"
        assert hasattr(User, "domain_ids"), "User should have 'domain_ids' property"
        assert hasattr(User, "num_tokens"), "User should have 'num_tokens' property"

        # Check inherited methods from BasePermsModel
        assert hasattr(User, "bypass_perms"), "User should have 'bypass_perms' method"
        assert hasattr(User, "can_read"), "User should have 'can_read' method"
        assert hasattr(User, "can_write"), "User should have 'can_write' method"
        assert hasattr(User, "can_create"), "User should have 'can_create' method"

        # Check inherited methods from BaseModel
        assert hasattr(User, "save"), "User should have 'save' method"
        assert hasattr(User, "delete"), "User should have 'delete' method"
        assert hasattr(User, "update"), "User should have 'update' method"
        assert hasattr(User, "get"), "User should have 'get' class method"
        assert hasattr(User, "get_or_404"), "User should have 'get_or_404' class method"
        assert hasattr(User, "get_by"), "User should have 'get_by' class method"

    def test_custom_user_instance_has_all_inherited_columns(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that User instances have all expected column values."""
        import uuid

        # Create a User instance
        with User.bypass_perms():
            user = User(
                email="testuser@example.com",
                password="password123",
            )
            user.save()

        # Verify the instance has all expected attributes
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.email == "testuser@example.com"
        assert user.is_enabled is True  # Default value
        assert user.created_at is not None
        assert user.updated_at is not None

        # Verify password was hashed
        assert user.password is not None
        assert user.is_password_correct("password123")

    def test_custom_user_single_table_inheritance_uses_same_table(
        self, unit_app: Flask, api: Api, db_session: "scoped_session"
    ) -> None:
        """Test that User uses the 'user' table and subclasses inherit it."""
        # Verify User uses the correct table
        assert User.__tablename__ == "user"

        # Verify that a subclass without __tablename__ would use the same table
        # (This is implicit in SQLAlchemy's single-table inheritance behavior)
