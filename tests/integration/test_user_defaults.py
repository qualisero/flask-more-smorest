"""Integration test: battery-included defaults scenario."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from flask_more_smorest import Api, db, init_db, init_jwt
from flask_more_smorest.error import ForbiddenError
from flask_more_smorest.perms import UserBlueprint, clear_registration, init_fms
from flask_more_smorest.perms.models.base_roles import BaseRoleEnum
from flask_more_smorest.perms.user_registry import (
    get_domain_model,
    get_role_model,
    get_setting_model,
    get_token_model,
    get_user_model,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from werkzeug.test import TestResponse

    from flask_more_smorest.perms.models.defaults import (
        Domain,
        Token,
        User,
        UserRole,
        UserSetting,
    )
else:
    # Runtime: declare as type[Any] placeholder, will be set by _load_defaults fixture
    # Using Any type for runtime placeholder; TYPE_CHECKING block provides proper types
    Domain: type[Any] = cast(type[Any], None)  # type: ignore[assignment]
    Token: type[Any] = cast(type[Any], None)  # type: ignore[assignment]
    User: type[Any] = cast(type[Any], None)  # type: ignore[assignment]
    UserRole: type[Any] = cast(type[Any], None)  # type: ignore[assignment]
    UserSetting: type[Any] = cast(type[Any], None)  # type: ignore[assignment]


@pytest.fixture(scope="module", autouse=True)
def _load_defaults() -> Iterator[None]:
    from flask_more_smorest.perms.models import defaults as defaults_module

    # We rely on conftest.py to have unloaded these modules if they were used in previous tests.
    # Just importing them here will create fresh classes if they were unloaded.
    # If they weren't unloaded (first test), they are fresh anyway.

    clear_registration()
    db.metadata.clear()

    # Note: We used to reload() here, but that caused duplicate registration warnings
    # and NoForeignKeysError because old classes remained in db.Model registry.
    # Since conftest.py handles unloading, we don't need to force reload here.

    global Domain, Token, User, UserRole, UserSetting  # type: ignore[misc]
    Domain = defaults_module.Domain  # type: ignore[misc]
    Token = defaults_module.Token  # type: ignore[misc]
    User = defaults_module.User  # type: ignore[misc]
    UserRole = defaults_module.UserRole  # type: ignore[misc]
    UserSetting = defaults_module.UserSetting  # type: ignore[misc]

    yield

    # Clear registry
    clear_registration()
    # Clear metadata
    db.metadata.clear()
    # Clear SQLAlchemy mappers
    with contextlib.suppress(Exception):
        import sqlalchemy as sa

        sa.orm.clear_mappers()
    # Unload user_schemas module - critical for preventing schema caching pollution
    import sys

    if "flask_more_smorest.perms.user_schemas" in sys.modules:
        del sys.modules["flask_more_smorest.perms.user_schemas"]


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Defaults API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "jwt-secret"

    init_fms()
    init_db(app)
    init_jwt(app)

    return app


@pytest.fixture
def db_session(app: Flask) -> Iterator[None]:
    """Create a database session for tests."""
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


# ============================================================================
# Helper Functions
# ============================================================================


def _create_user_with_role(email: str, role: BaseRoleEnum = BaseRoleEnum.USER, password: str = "secret") -> Any:
    """Helper to create a user with a role."""
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    domain = Domain(name=f"domain-{user.id}", display_name=f"Domain {user.id}", active=True)
    db.session.add(domain)
    db.session.flush()

    user_role = UserRole(user_id=user.id, domain_id=domain.id, role=role)
    db.session.add(user_role)
    db.session.commit()
    return user


# ============================================================================
# Tests
# ============================================================================


def test_defaults_user_blueprint_login(app: Flask, db_session: None) -> None:
    """Test default user blueprint login endpoint."""
    api: Api = Api(app)
    user_bp: UserBlueprint = UserBlueprint(register=False)
    api.register_blueprint(user_bp)

    user = User(email="alice@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    client: FlaskClient = app.test_client()
    resp: TestResponse = client.post("/api/users/login/", json={"email": "alice@example.com", "password": "secret"})
    assert resp.status_code == 200
    payload: dict[str, str] = resp.get_json()
    assert payload["token_type"] == "bearer"

    token: str = payload["access_token"]
    me_resp: TestResponse = client.get("/api/users/me/", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me = me_resp.get_json()
    assert me["email"] == "alice@example.com"


def test_defaults_related_models(app: Flask, db_session: None) -> None:
    """Test relationships between default models."""
    user = User(email="bob@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    domain = Domain(name="main", display_name="Main", active=True)
    db.session.add(domain)
    db.session.flush()

    role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.ADMIN)
    token = Token(user_id=user.id, token=str(uuid.uuid4()))
    setting = UserSetting(user_id=user.id, key="theme", value="dark")

    db.session.add_all([role, token, setting])
    db.session.commit()

    db.session.refresh(user)
    assert len(user.roles) == 1
    assert len(user.tokens) == 1
    assert len(user.settings) == 1
    assert isinstance(user.roles[0], UserRole)
    assert isinstance(user.tokens[0], Token)
    assert isinstance(user.settings[0], UserSetting)
    assert user.roles[0].user is user
    assert user.tokens[0].user is user
    assert user.settings[0].user is user
    assert user.roles[0].role == "ADMIN"
    assert user.has_role(BaseRoleEnum.ADMIN)
    assert user.has_domain_access(domain.id)


def test_defaults_get_current_user_with_jwt(app: Flask, db_session: None) -> None:
    """Test get_current_user with JWT authentication."""
    user = User(email="carol@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    token: str = create_access_token(identity=str(user.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        current = User.get_current_user()
        assert current is not None
        assert current.id == user.id


def test_defaults_cascade_delete(app: Flask, db_session: None) -> None:
    """Test cascade delete deletes related models."""
    user = User(email="dana@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    role = UserRole(user_id=user.id, domain_id=None, role=BaseRoleEnum.USER)
    token = Token(user_id=user.id, token=str(uuid.uuid4()))
    setting = UserSetting(user_id=user.id, key="theme", value="dark")

    db.session.add_all([role, token, setting])
    db.session.commit()

    # Authenticate as the user to perform delete operation
    jwt_token = create_access_token(identity=str(user.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {jwt_token}"}):
        user.delete(commit=True)

    remaining_roles = db.session.query(UserRole).count()
    remaining_tokens = db.session.query(Token).count()
    remaining_settings = db.session.query(UserSetting).count()

    assert remaining_roles == 0
    assert remaining_tokens == 0
    assert remaining_settings == 0


def test_defaults_user_read_permissions(app: Flask, db_session: None) -> None:
    """Test user read permissions."""
    user = User(email="user@example.com")
    user.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    other_user = User(email="other@example.com")
    db.session.add_all([user, other_user])
    db.session.commit()

    # Test within request context for proper permission checking
    with app.test_request_context():
        # User can read themselves
        assert user.can_read(user) is True
        # Admin can read any user
        assert user.can_read(admin) is True
        # Another user cannot read
        assert user.can_read(other_user) is False
        # Unauthenticated cannot read
        assert user.can_read(None) is False


def test_defaults_user_write_permissions(app: Flask, db_session: None) -> None:
    """Test user write permissions."""
    user = User(email="user@example.com")
    user.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    other_user = User(email="other@example.com")
    db.session.add_all([user, other_user])
    db.session.commit()

    # Test within request context for proper permission checking
    with app.test_request_context():
        # User can edit themselves
        assert user.can_write(user) is True
        # Admin can edit non-admin users
        assert user.can_write(admin) is True
        # Another user cannot write
        assert user.can_write(other_user) is False
        # Unauthenticated cannot write
        assert user.can_write(None) is False


def test_defaults_user_create_permissions(app: Flask, db_session: None) -> None:
    """Test user create permissions."""
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.commit()

    new_user = User(email="new@example.com")

    # Admin can create users
    assert new_user._can_create(admin) is True
    # Unauthenticated cannot create
    assert new_user._can_create(None) is False  # fail without PUBLIC_REGISTRATION


def test_defaults_domain_read_permissions(app: Flask, db_session: None) -> None:
    """Test domain read permissions (anyone can read)."""
    domain = Domain(name="test", display_name="Test", active=True)
    db.session.add(domain)
    db.session.commit()

    # Anyone can read domains
    assert domain._can_read(None) is True
    assert domain._can_read(User(email="user@example.com")) is True


def test_defaults_role_write_permissions(app: Flask, db_session: None) -> None:
    """Test role write permissions."""
    user = User(email="user@example.com")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    superadmin = _create_user_with_role("super@example.com", BaseRoleEnum.SUPERADMIN)
    db.session.add(user)
    db.session.commit()

    domain = Domain(name="main", display_name="Main", active=True)
    db.session.add(domain)
    db.session.flush()

    # Admin role
    admin_role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.ADMIN)
    # User role
    user_role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.USER)
    db.session.add_all([admin_role, user_role])
    db.session.commit()

    # Superadmin can modify admin roles
    assert admin_role._can_write(superadmin) is True
    # Admin cannot modify admin roles
    assert admin_role._can_write(admin) is False
    # Admin can modify user roles
    assert user_role._can_write(admin) is True


def test_defaults_role_create_permissions(app: Flask, db_session: None) -> None:
    """Test role create permissions."""
    user = User(email="user@example.com")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add(user)
    db.session.commit()

    domain = Domain(name="main", display_name="Main", active=True)
    db.session.add(domain)
    db.session.flush()

    # Admin role
    admin_role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.ADMIN)
    # User role
    user_role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.USER)

    token = create_access_token(identity=str(admin.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        # Admin cannot create admin roles
        assert admin_role._can_create(admin) is False
        # Admin can create user roles
        assert user_role._can_create(admin) is True


def test_defaults_role_read_permissions(app: Flask, db_session: None) -> None:
    """Test role read permissions (delegates to user)."""
    user = User(email="user@example.com")
    user.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add(user)
    db.session.commit()

    domain = Domain(name="main", display_name="Main", active=True)
    db.session.add(domain)
    db.session.flush()

    role = UserRole(user_id=user.id, domain_id=domain.id, role=BaseRoleEnum.USER)
    db.session.add(role)
    db.session.commit()

    # User can read their own role
    assert role.can_read(user) is True
    # Admin can read role
    assert role.can_read(admin) is True

    # Test within request context for unauthenticated check
    with app.test_request_context():
        assert role.can_read(None) is False


def test_defaults_token_permissions_with_bypass(app: Flask, db_session: None) -> None:
    """Test token permissions delegate to user."""
    owner = User(email="owner@example.com")
    owner.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add_all([owner, other])
    db.session.commit()

    token = Token(user_id=owner.id, token=str(uuid.uuid4()))
    db.session.add(token)
    db.session.commit()

    # Outside request context, permissions are bypassed
    assert token.can_read(owner) is True
    assert token.can_write(owner) is True

    # Within request context with proper delegation
    with app.test_request_context():
        # Owner can read/write their token (delegates to user._can_write)
        assert token.can_read(owner) is True
        assert token.can_write(owner) is True

        # Admin can read/write another user's token (delegates to user._can_write which allows admin)
        assert token.can_read(admin) is True
        assert token.can_write(admin) is True

        # Other user cannot read/write
        assert token.can_read(other) is False
        assert token.can_write(other) is False

        # Unauthenticated cannot read/write
        assert token.can_read(None) is False
        assert token.can_write(None) is False

    # With bypass_perms context, all checks pass
    with Token.bypass_perms():
        assert token.can_read(other) is True
        assert token.can_write(other) is True


def test_defaults_token_create_permissions(app: Flask, db_session: None) -> None:
    """Test token create permissions delegate to user."""
    owner = User(email="owner@example.com")
    owner.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret_other")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add_all([owner, other])
    db.session.commit()

    # Token for owner
    owner_token = Token(user_id=owner.id, token=str(uuid.uuid4()))

    # Test within request context with authentication

    # 1. Owner can create their own token
    token = create_access_token(identity=str(owner.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_token.can_create(owner) is True

    # 2. Other user cannot create token for owner (no write permission or cannot read user)
    token = create_access_token(identity=str(other.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_token.can_create(other) is False

    # 3. Admin can create token for any user
    token = create_access_token(identity=str(admin.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_token.can_create(admin) is True

    # 4. Unauthenticated cannot create
    with app.test_request_context():
        assert owner_token.can_create(None) is False


def test_defaults_setting_permissions_with_bypass(app: Flask, db_session: None) -> None:
    """Test setting permissions delegate to user."""
    owner = User(email="owner@example.com")
    owner.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add_all([owner, other])
    db.session.commit()

    setting = UserSetting(user_id=owner.id, key="theme", value="dark")
    db.session.add(setting)
    db.session.commit()

    # Outside request context, permissions are bypassed
    assert setting.can_read(owner) is True
    assert setting.can_write(owner) is True

    # Within request context with proper delegation
    with app.test_request_context():
        # Owner can read/write their setting (delegates to user._can_write)
        assert setting.can_read(owner) is True
        assert setting.can_write(owner) is True

        # Admin can read/write another user's setting (delegates to user._can_write which allows admin)
        assert setting.can_read(admin) is True
        assert setting.can_write(admin) is True

        # Other user cannot read/write
        assert setting.can_read(other) is False
        assert setting.can_write(other) is False

        # Unauthenticated cannot read/write
        assert setting.can_read(None) is False
        assert setting.can_write(None) is False

    # With bypass_perms context, all checks pass
    with UserSetting.bypass_perms():
        assert setting.can_read(other) is True
        assert setting.can_write(other) is True


def test_defaults_setting_create_permissions(app: Flask, db_session: None) -> None:
    """Test setting create permissions delegate to user."""
    owner = User(email="owner@example.com")
    owner.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add_all([owner, other])
    db.session.commit()

    # Setting for owner
    owner_setting = UserSetting(user_id=owner.id, key="theme", value="dark")
    db.session.add(owner_setting)
    db.session.commit()

    # Test within request context with authentication

    # 1. Owner can create their own setting
    token = create_access_token(identity=str(owner.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_setting.can_create(owner) is True

    # 2. Other user cannot create setting for owner
    token = create_access_token(identity=str(other.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_setting.can_create(other) is False

    # 3. Admin can create setting for any user
    token = create_access_token(identity=str(admin.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert owner_setting.can_create(admin) is True

    # 4. Unauthenticated cannot create
    with app.test_request_context():
        assert owner_setting.can_create(None) is False


def test_defaults_permission_methods_with_jwt(app: Flask, db_session: None) -> None:
    """Test can_read/can_write methods with JWT authentication."""
    owner = User(email="owner@example.com")
    owner.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret")
    admin = _create_user_with_role("admin@example.com", BaseRoleEnum.ADMIN)
    db.session.add_all([owner, other])
    db.session.commit()

    # Owner's resources
    owner_token = Token(user_id=owner.id, token=str(uuid.uuid4()))
    owner_setting = UserSetting(user_id=owner.id, key="theme", value="dark")
    # Other user's resources
    other_token = Token(user_id=other.id, token=str(uuid.uuid4()))
    other_setting = UserSetting(user_id=other.id, key="theme", value="light")
    db.session.add_all([owner_token, owner_setting, other_token, other_setting])
    db.session.commit()

    owner_token_id = owner_token.id
    owner_setting_id = owner_setting.id
    other_token_id = other_token.id
    other_setting_id = other_setting.id
    jwt_token: str = create_access_token(identity=str(owner.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {jwt_token}"}):
        # Owner can read/write their own resources (delegates to user._can_write)
        bound_owner_token = db.session.get(Token, owner_token_id)
        bound_owner_setting = db.session.get(UserSetting, owner_setting_id)
        assert bound_owner_token is not None
        assert bound_owner_setting is not None
        assert bound_owner_token.can_read() is True
        assert bound_owner_token.can_write() is True
        assert bound_owner_setting.can_read() is True
        assert bound_owner_setting.can_write() is True

        # Owner cannot read/write other's resources
        bound_other_token = db.session.get(Token, other_token_id)
        bound_other_setting = db.session.get(UserSetting, other_setting_id)
        assert bound_other_token is not None
        assert bound_other_setting is not None
        assert bound_other_token.can_read() is False
        assert bound_other_token.can_write() is False
        assert bound_other_setting.can_read() is False
        assert bound_other_setting.can_write() is False

    # Admin should be able to read/write user's resources
    admin_jwt_token: str = create_access_token(identity=str(admin.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {admin_jwt_token}"}):
        admin_bound_owner_token = db.session.get(Token, owner_token_id)
        admin_bound_owner_setting = db.session.get(UserSetting, owner_setting_id)
        admin_bound_other_token = db.session.get(Token, other_token_id)
        admin_bound_other_setting = db.session.get(UserSetting, other_setting_id)
        assert admin_bound_owner_token is not None
        assert admin_bound_owner_setting is not None
        assert admin_bound_other_token is not None
        assert admin_bound_other_setting is not None
        # Admin can read/write any user's tokens/settings (delegates to user._can_write which allows admin)
        assert admin_bound_owner_token.can_read() is True
        assert admin_bound_owner_token.can_write() is True
        assert admin_bound_owner_setting.can_read() is True
        assert admin_bound_owner_setting.can_write() is True
        assert admin_bound_other_token.can_read() is True
        assert admin_bound_other_token.can_write() is True
        assert admin_bound_other_setting.can_read() is True
        assert admin_bound_other_setting.can_write() is True


def test_defaults_permission_enforcement_with_forbidden_errors(app: Flask, db_session: None) -> None:
    """Test that permission violations raise ForbiddenError."""
    user = User(email="user@example.com")
    user.set_password("secret")
    other = User(email="other@example.com")
    other.set_password("secret")
    db.session.add_all([user, other])
    db.session.commit()

    # Create token for other user
    token = Token(user_id=other.id, token=str(uuid.uuid4()))
    db.session.add(token)
    db.session.commit()

    token_id = token.id
    jwt_token: str = create_access_token(identity=str(user.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {jwt_token}"}):
        bound_token = db.session.get(Token, token_id)
        assert bound_token is not None

        # User cannot read other's token (delegates to user._can_write)
        assert bound_token.can_read() is False

        # Attempting to save should raise ForbiddenError
        with pytest.raises(ForbiddenError):
            bound_token.save()


def test_defaults_type_helpers() -> None:
    """Test type helper functions."""
    init_fms()

    assert get_user_model(User) is User
    assert get_role_model(UserRole) is UserRole
    assert get_token_model(Token) is Token
    assert get_domain_model(Domain) is Domain
    assert get_setting_model(UserSetting) is UserSetting

    # Type checks moved to TYPE_CHECKING block to avoid runtime variable issues


def test_init_fms_auto_loads_all_defaults() -> None:
    """Test that init_fms() with no arguments auto-loads all default models.

    This verifies the auto-loading behavior: when you call init_fms() without
    any arguments, it automatically imports and registers User, UserRole, Token,
    Domain, and UserSetting from flask_more_smorest.perms.models.defaults.
    No explicit import of default models is required.
    """
    # Clear any previous registration
    clear_registration()

    # Call init_fms() with NO arguments - should auto-load all defaults
    init_fms()

    # Import defaults module (should already be auto-loaded by init_fms)
    from flask_more_smorest.perms.models.defaults import (
        Domain,
        Token,
        User,
        UserRole,
        UserSetting,
    )

    # Verify all default models were registered
    assert get_user_model(User) is User
    assert get_role_model(UserRole) is UserRole
    assert get_token_model(Token) is Token
    assert get_domain_model(Domain) is Domain
    assert get_setting_model(UserSetting) is UserSetting

    # Re-clear for other tests
    clear_registration()


def test_defaults_current_user_none_when_not_authenticated(app: Flask, db_session: None) -> None:
    """Test get_current_user returns None when not authenticated."""
    with app.app_context():
        db.create_all()
        user = User(email="test@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

    with app.test_request_context():
        current = User.get_current_user()
        assert current is None
