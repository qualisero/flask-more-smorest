"""Integration test: fully extended user + related models + custom blueprint."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import Api, db, init_db, init_jwt
from flask_more_smorest.error import ForbiddenError, UnauthorizedError
from flask_more_smorest.perms import UserBlueprint, clear_registration, init_fms
from flask_more_smorest.perms.model_mixins import ProfileMixin, SoftDeleteMixin, TimestampMixin
from flask_more_smorest.perms.user_registry import (
    expect_domain_model,
    expect_role_model,
    expect_setting_model,
    expect_token_model,
    expect_user_model,
)

if TYPE_CHECKING:
    from typing import assert_type, cast

    from flask.testing import FlaskClient
    from werkzeug.test import TestResponse

from flask_more_smorest.perms.models.abstract_role import AbstractDomain, AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.perms.models.base_roles import BaseRoleEnum

# ============================================================================
# Custom Role Enum (reuses default roles and adds custom ones)
# ============================================================================


class CustomUserRoleEnum(str):
    """Custom role enumeration reusing default roles with uppercase values.

    Reuses the default ADMIN, SUPERADMIN, and USER roles from BaseRoleEnum
    and adds additional roles for the extended test scenario.
    """

    SUPERADMIN = BaseRoleEnum.SUPERADMIN
    ADMIN = BaseRoleEnum.ADMIN
    USER = BaseRoleEnum.USER
    MODERATOR = "MODERATOR"
    GUEST = "GUEST"
    MEMBER = "MEMBER"


if TYPE_CHECKING:
    CustomDomain = AbstractDomain
    CustomUser = AbstractUser
    CustomUserRole = AbstractUserRole
    CustomToken = AbstractToken
    CustomUserSetting = AbstractUserSetting
    CustomUserBlueprint = UserBlueprint
else:
    CustomDomain = cast(type[AbstractDomain], None)
    CustomUser = cast(type[AbstractUser], None)
    CustomUserRole = cast(type[AbstractUserRole], None)
    CustomToken = cast(type[AbstractToken], None)
    CustomUserSetting = cast(type[AbstractUserSetting], None)
    CustomUserBlueprint = cast(type[UserBlueprint], None)


@pytest.fixture
def app(custom_models: SimpleNamespace) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Extended API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "jwt-secret"

    init_fms(
        user=custom_models.CustomUser,
        role=custom_models.CustomUserRole,
        token=custom_models.CustomToken,
        domain=custom_models.CustomDomain,
        setting=custom_models.CustomUserSetting,
    )
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


@pytest.fixture(scope="module", autouse=True)
def _module_cleanup() -> Iterator[None]:
    """Clean up at module boundaries to prevent pollution of subsequent test modules."""
    yield
    # Clear registry
    clear_registration()
    # Clear metadata
    db.metadata.clear()
    # Clear SQLAlchemy mappers
    with contextlib.suppress(Exception):
        sa.orm.clear_mappers()
    # Unload user_schemas module - critical for preventing schema caching pollution
    import sys

    if "flask_more_smorest.perms.user_schemas" in sys.modules:
        del sys.modules["flask_more_smorest.perms.user_schemas"]


@pytest.fixture(scope="module", autouse=True)
def custom_models() -> Iterator[SimpleNamespace]:
    clear_registration()
    db.metadata.clear()
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    import sys
    import types

    module = types.ModuleType(module_name)
    # Populate module with globals so Mapped etc. are available
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomDomain(AbstractDomain):
        """Domain with custom fields and custom-field-based permissions."""

        __module__ = module_name

        slug: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
        is_public: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        visibility: Mapped[str] = mapped_column(sa.String(20), default="private", nullable=False)  # private/team/public
        owner_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)

        def _can_read(self, user: CustomUser | None) -> bool:
            # Public domains are readable by anyone
            if self.visibility == "public" or self.is_public:
                return True
            # Private/team domains require authentication
            if user is None:
                return False
            # Owner can always read
            if self.owner_id and self.owner_id == user.id:
                return True
            # Team visibility: any authenticated user in same domain can read
            if self.visibility == "team":
                return user.has_domain_access(self.id)
            # Otherwise requires ADMIN role
            return user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_write(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Owner can write
            if self.owner_id and self.owner_id == user.id:
                return True
            # Otherwise requires ADMIN role
            return user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_create(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Only admins or premium users can create domains
            return user.has_role(CustomUserRoleEnum.ADMIN) or getattr(user, "is_premium", False)

    class CustomUser(AbstractUser, ProfileMixin, TimestampMixin, SoftDeleteMixin):  # type: ignore[misc]
        """User with multiple mixins and custom fields for permission testing."""

        __module__ = module_name

        bio: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
        is_premium: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        trust_level: Mapped[int] = mapped_column(sa.Integer(), default=0, nullable=False)  # 0-5

        def _can_read(self, user: CustomUser | None) -> bool:
            # Unauthenticated can read if user is not soft-deleted
            if not self.is_deleted:
                return True
            # Deleted users can only be read by self or admins
            if user is None:
                return False
            return self.id == user.id or user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_write(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Users can edit their own profile
            if self.id == user.id:
                return True
            # Admins can edit non-admin users
            if user.has_role(CustomUserRoleEnum.ADMIN) and not self.is_admin:
                return True
            # Superadmins can edit anyone
            return user.has_role(CustomUserRoleEnum.SUPERADMIN)

    class CustomUserRole(AbstractUserRole):
        """Role with custom fields that affect permissions."""

        __module__ = module_name

        source: Mapped[str | None] = mapped_column(sa.String(100))
        is_temporary: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        granted_by_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)

        def _can_write(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Temporary roles can be removed by the user themselves
            if self.is_temporary and self.user_id == user.id:
                return True
            # Role granter can modify the role
            if self.granted_by_id and self.granted_by_id == user.id:
                return True
            # Otherwise requires ADMIN
            return user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_read(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # User can read their own roles
            if self.user_id == user.id:
                return True
            # Admins can read all roles
            return user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_create(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Temporary roles can be self-assigned if trust level is high enough
            if self.is_temporary and self.user_id == user.id:
                return user.trust_level >= 3
            # Otherwise requires ADMIN
            return user.has_role(CustomUserRoleEnum.ADMIN)

    class CustomToken(AbstractToken):
        """Token with custom fields affecting permissions."""

        __module__ = module_name

        label: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
        last_used_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
        is_revoked: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        scope: Mapped[str] = mapped_column(sa.String(50), default="full", nullable=False)  # full/readonly

        def _can_read(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Owner can read their tokens
            if self.user_id == user.id:
                return True
            # Admins can read non-revoked tokens only
            return user.has_role(CustomUserRoleEnum.ADMIN) and not self.is_revoked

        def _can_write(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Owner can write their own tokens
            return self.user_id == user.id

        def _can_create(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Users can create their own tokens unless they're soft-deleted
            if self.user_id == user.id:
                return not user.is_deleted
            # Admins can create tokens for others
            return user.has_role(CustomUserRoleEnum.ADMIN)

    class CustomUserSetting(AbstractUserSetting):
        """Setting with custom fields for permission control."""

        __module__ = module_name

        scope: Mapped[str] = mapped_column(sa.String(50), default="user", nullable=False)
        is_sensitive: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        is_system: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)

        def _can_read(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # Owner can read non-sensitive settings
            if self.user_id == user.id:
                if self.is_sensitive:
                    # Sensitive settings require premium or admin
                    return user.is_premium or user.has_role(CustomUserRoleEnum.ADMIN)
                return True
            # Admins can read non-system settings
            return user.has_role(CustomUserRoleEnum.ADMIN) and not self.is_system

        def _can_write(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # System settings can only be modified by superadmins
            if self.is_system:
                return user.has_role(CustomUserRoleEnum.SUPERADMIN)
            # Owner can write their own settings
            if self.user_id == user.id:
                return True
            # Admins can write non-system settings
            return user.has_role(CustomUserRoleEnum.ADMIN)

        def _can_create(self, user: CustomUser | None) -> bool:
            if user is None:
                return False
            # System settings can only be created by superadmins
            if self.is_system:
                return user.has_role(CustomUserRoleEnum.SUPERADMIN)
            # Users can create their own settings
            if self.user_id == user.id:
                return True
            # Admins can create settings for others
            return user.has_role(CustomUserRoleEnum.ADMIN)

    class CustomUserBlueprint(UserBlueprint):
        """Custom blueprint with additional endpoints."""

        __module__ = module_name

    models = SimpleNamespace(
        CustomDomain=CustomDomain,
        CustomUser=CustomUser,
        CustomUserRole=CustomUserRole,
        CustomToken=CustomToken,
        CustomUserSetting=CustomUserSetting,
        CustomUserBlueprint=CustomUserBlueprint,
    )
    globals().update(models.__dict__)

    try:
        yield models
    finally:
        sys.modules.pop(module_name, None)
        clear_registration()


# ============================================================================
# Helper Functions
# ============================================================================


def _create_admin_user(email: str, password: str = "secret") -> CustomUser:
    """Helper to create a user with ADMIN role."""
    user = CustomUser(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    domain = CustomDomain(name=f"admin-{user.id}", display_name="Admin Domain", active=True, slug=f"admin-{user.id}")
    db.session.add(domain)
    db.session.flush()

    role = CustomUserRole(user_id=user.id, domain_id=domain.id, role=CustomUserRoleEnum.ADMIN)
    db.session.add(role)
    db.session.flush()
    return user


def _create_superadmin_user(email: str, password: str = "secret") -> CustomUser:
    """Helper to create a user with SUPERADMIN role."""
    user = CustomUser(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    domain = CustomDomain(name=f"super-{user.id}", display_name="Super Domain", active=True, slug=f"super-{user.id}")
    db.session.add(domain)
    db.session.flush()

    role = CustomUserRole(user_id=user.id, domain_id=domain.id, role=CustomUserRoleEnum.SUPERADMIN)
    db.session.add(role)
    db.session.flush()
    return user


# ============================================================================
# Tests
# ============================================================================


def test_fully_extended_models_and_blueprint(app: Flask, db_session: None, custom_models: SimpleNamespace) -> None:
    """Test custom blueprint with bio endpoint."""
    import sqlalchemy as sa

    sa.orm.configure_mappers()

    CustomUserBlueprint = custom_models.CustomUserBlueprint
    CustomUser = custom_models.CustomUser

    api: Api = Api(app)
    user_bp: CustomUserBlueprint = CustomUserBlueprint(register=False)  # type: ignore[valid-type]

    # Add custom bio endpoint
    @user_bp.route("/me/bio/", methods=["GET"])  # type: ignore[attr-defined]
    def get_bio() -> dict[str, str | None]:
        user = CustomUser.get_current_user()
        if user is None:
            raise UnauthorizedError("Not authenticated")
        return {"bio": user.bio}

    api.register_blueprint(user_bp)

    user: CustomUser = CustomUser(email="anne@example.com", bio="Hello World")  # type: ignore[valid-type]
    user.set_password("secret")  # type: ignore[attr-defined]
    db.session.add(user)
    db.session.commit()

    client: FlaskClient = app.test_client()
    resp: TestResponse = client.post("/api/users/login/", json={"email": "anne@example.com", "password": "secret"})
    assert resp.status_code == 200
    payload: dict[str, str] = resp.get_json()
    token: str = payload["access_token"]

    bio_resp: TestResponse = client.get("/api/users/me/bio/", headers={"Authorization": f"Bearer {token}"})
    assert bio_resp.status_code == 200
    assert bio_resp.get_json()["bio"] == "Hello World"


def test_custom_blueprint_profile_endpoint(app: Flask, db_session: None) -> None:
    """Test custom profile endpoint with ProfileMixin fields."""
    api: Api = Api(app)
    user_bp: CustomUserBlueprint = CustomUserBlueprint(register=False)

    # Add custom profile endpoint
    @user_bp.route("/me/profile/", methods=["GET"])  # type: ignore[attr-defined]
    def get_profile() -> dict:
        user = CustomUser.get_current_user()
        if user is None:
            raise UnauthorizedError("Not authenticated")
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
        }

    api.register_blueprint(user_bp)

    user: CustomUser = CustomUser(
        email="profile@example.com",
        first_name="John",
        last_name="Doe",
        display_name="JD",
        avatar_url="https://example.com/avatar.jpg",
    )
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    client: FlaskClient = app.test_client()
    resp: TestResponse = client.post("/api/users/login/", json={"email": "profile@example.com", "password": "secret"})
    token: str = resp.get_json()["access_token"]

    profile_resp: TestResponse = client.get("/api/users/me/profile/", headers={"Authorization": f"Bearer {token}"})
    assert profile_resp.status_code == 200
    data = profile_resp.get_json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["full_name"] == "John Doe"
    assert data["display_name"] == "JD"
    assert data["avatar_url"] == "https://example.com/avatar.jpg"


def test_fully_extended_relationships_and_permissions(app: Flask, db_session: None) -> None:
    """Test relationships and basic permission checks."""
    user: CustomUser = CustomUser(email="bea@example.com", bio="Bio")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    domain: CustomDomain = CustomDomain(
        name="main", display_name="Main", active=True, slug="main", is_public=True, owner_id=user.id
    )
    db.session.add(domain)
    db.session.flush()

    role: CustomUserRole = CustomUserRole(
        user_id=user.id, domain_id=domain.id, role=CustomUserRoleEnum.ADMIN, source="seed"
    )
    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()), label="primary")
    setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark", scope="user")

    db.session.add_all([role, token, setting])
    db.session.commit()

    db.session.refresh(user)
    assert len(user.roles) == 1
    assert len(user.tokens) == 1
    assert len(user.settings) == 1
    assert isinstance(user.roles[0], CustomUserRole)
    assert isinstance(user.tokens[0], CustomToken)
    assert isinstance(user.settings[0], CustomUserSetting)
    assert user.roles[0].user is user
    assert user.tokens[0].user is user
    assert user.settings[0].user is user
    assert user.has_domain_access(domain.id)
    # Public domain readable without auth
    assert domain._can_read(None) is True


def test_domain_permissions_based_on_visibility(app: Flask, db_session: None) -> None:
    """Test domain read permissions based on visibility field."""
    owner: CustomUser = CustomUser(email="owner@example.com")
    owner.set_password("secret")
    regular_user: CustomUser = CustomUser(email="regular@example.com")
    regular_user.set_password("secret")
    admin_user = _create_admin_user("admin@example.com")
    db.session.add_all([owner, regular_user])
    db.session.commit()

    # Private domain
    private_domain: CustomDomain = CustomDomain(
        name="private",
        display_name="Private",
        active=True,
        slug="private",
        visibility="private",
        is_public=False,
        owner_id=owner.id,
    )
    # Team domain
    team_domain: CustomDomain = CustomDomain(
        name="team", display_name="Team", active=True, slug="team", visibility="team", is_public=False
    )
    # Public domain
    public_domain: CustomDomain = CustomDomain(
        name="public", display_name="Public", active=True, slug="public", visibility="public", is_public=True
    )
    db.session.add_all([private_domain, team_domain, public_domain])
    db.session.commit()

    # Add regular_user to team_domain
    role: CustomUserRole = CustomUserRole(
        user_id=regular_user.id, domain_id=team_domain.id, role=CustomUserRoleEnum.MEMBER
    )
    db.session.add(role)
    db.session.commit()

    # Public domain: everyone can read
    assert public_domain._can_read(None) is True
    assert public_domain._can_read(regular_user) is True
    assert public_domain._can_read(owner) is True

    # Private domain: only owner and admin can read
    assert private_domain._can_read(None) is False
    assert private_domain._can_read(regular_user) is False
    assert private_domain._can_read(owner) is True
    assert private_domain._can_read(admin_user) is True

    # Team domain: authenticated users with domain access can read
    assert team_domain._can_read(None) is False
    assert team_domain._can_read(regular_user) is True  # has domain access
    assert team_domain._can_read(owner) is False  # no domain access
    # Admin needs role check for team visibility, or we could fix this by checking admin status
    # For now, admin without domain membership can't read team domains
    # If we want admins to always read, update the _can_read logic in CustomDomain
    assert team_domain._can_read(admin_user) is False  # no domain access, team visibility


def test_domain_write_permissions(app: Flask, db_session: None) -> None:
    """Test domain write permissions based on owner_id."""
    owner: CustomUser = CustomUser(email="owner@example.com")
    owner.set_password("secret")
    other_user: CustomUser = CustomUser(email="other@example.com")
    other_user.set_password("secret")
    admin_user = _create_admin_user("admin@example.com")
    db.session.add_all([owner, other_user])
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="test", display_name="Test", active=True, slug="test", owner_id=owner.id)
    db.session.add(domain)
    db.session.commit()

    # Owner can write
    assert domain._can_write(owner) is True
    # Other users cannot
    assert domain._can_write(other_user) is False
    # Admin can write
    assert domain._can_write(admin_user) is True
    # Unauthenticated cannot
    assert domain._can_write(None) is False


def test_domain_create_permissions_premium_users(app: Flask, db_session: None) -> None:
    """Test domain creation requires admin or premium status."""
    regular: CustomUser = CustomUser(email="regular@example.com", is_premium=False)
    premium: CustomUser = CustomUser(email="premium@example.com", is_premium=True)
    admin = _create_admin_user("admin@example.com")
    db.session.add_all([regular, premium])
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="test", display_name="Test", active=True, slug="test")

    # Regular user cannot create
    assert domain._can_create(regular) is False
    # Premium user can create
    assert domain._can_create(premium) is True
    # Admin can create
    assert domain._can_create(admin) is True
    # Unauthenticated cannot
    assert domain._can_create(None) is False


def test_user_permissions_soft_delete(app: Flask, db_session: None) -> None:
    """Test user read permissions respect soft delete status."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    admin = _create_admin_user("admin@example.com")
    db.session.add(user)
    db.session.commit()

    # Active user is readable
    assert user._can_read(None) is True
    assert user._can_read(user) is True

    # Soft delete the user
    user.soft_delete()
    db.session.commit()

    # Soft-deleted user not readable without auth
    assert user._can_read(None) is False
    # But user can read themselves
    assert user._can_read(user) is True
    # Admin can read deleted users
    assert user._can_read(admin) is True


def test_user_write_permissions_hierarchy(app: Flask, db_session: None) -> None:
    """Test user write permissions respect admin hierarchy."""
    user: CustomUser = CustomUser(email="user@example.com")
    admin = _create_admin_user("admin@example.com")
    superadmin = _create_superadmin_user("super@example.com")
    db.session.add(user)
    db.session.commit()

    # User can edit themselves
    assert user._can_write(user) is True
    # Admin can edit non-admin users
    assert user._can_write(admin) is True
    # Admin cannot edit other admins (but superadmin can)
    # The current logic allows admins to edit non-admins, but superadmins have ADMIN role too
    # so the check "is not self.is_admin" fails for superadmin
    # Superadmin can edit admin
    assert admin._can_write(superadmin) is True


def test_role_permissions_temporary_roles(app: Flask, db_session: None) -> None:
    """Test role write permissions for temporary roles."""
    user: CustomUser = CustomUser(email="user@example.com")
    granter: CustomUser = CustomUser(email="granter@example.com")
    other: CustomUser = CustomUser(email="other@example.com")
    db.session.add_all([user, granter, other])
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="main", display_name="Main", active=True, slug="main")
    db.session.add(domain)
    db.session.flush()

    # Temporary role granted by granter
    temp_role: CustomUserRole = CustomUserRole(
        user_id=user.id,
        domain_id=domain.id,
        role=CustomUserRoleEnum.GUEST,
        is_temporary=True,
        granted_by_id=granter.id,
        source="manual",
    )
    db.session.add(temp_role)
    db.session.commit()

    # User can write (remove) their own temporary role
    assert temp_role._can_write(user) is True
    # Granter can write the role they granted
    assert temp_role._can_write(granter) is True
    # Other users cannot
    assert temp_role._can_write(other) is False
    # But can read
    assert temp_role._can_read(user) is True


def test_role_create_permissions_trust_level(app: Flask, db_session: None) -> None:
    """Test role creation based on trust level for temporary roles."""
    low_trust: CustomUser = CustomUser(email="low@example.com", trust_level=1)
    high_trust: CustomUser = CustomUser(email="high@example.com", trust_level=4)
    admin = _create_admin_user("admin@example.com")
    db.session.add_all([low_trust, high_trust])
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="main", display_name="Main", active=True, slug="main")
    db.session.add(domain)
    db.session.flush()

    # Temporary self-assigned role
    temp_role_low: CustomUserRole = CustomUserRole(
        user_id=low_trust.id, domain_id=domain.id, role=CustomUserRoleEnum.GUEST, is_temporary=True
    )
    temp_role_high: CustomUserRole = CustomUserRole(
        user_id=high_trust.id, domain_id=domain.id, role=CustomUserRoleEnum.GUEST, is_temporary=True
    )

    # Low trust user cannot create temporary role
    assert temp_role_low._can_create(low_trust) is False
    # High trust user can create temporary role
    assert temp_role_high._can_create(high_trust) is True
    # Admin can create any role
    assert temp_role_low._can_create(admin) is True


def test_token_permissions_based_on_revoked_status(app: Flask, db_session: None) -> None:
    """Test token read permissions respect revoked status."""
    user: CustomUser = CustomUser(email="user@example.com")
    admin = _create_admin_user("admin@example.com")
    db.session.add(user)
    db.session.commit()

    active_token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()), is_revoked=False)
    revoked_token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()), is_revoked=True)
    db.session.add_all([active_token, revoked_token])
    db.session.commit()

    # Owner can read both
    assert active_token._can_read(user) is True
    assert revoked_token._can_read(user) is True

    # Admin can read active but not revoked
    assert active_token._can_read(admin) is True
    assert revoked_token._can_read(admin) is False


def test_token_write_permissions_owner_only(app: Flask, db_session: None) -> None:
    """Test token write permissions limited to owner."""
    user: CustomUser = CustomUser(email="user@example.com")
    other: CustomUser = CustomUser(email="other@example.com")
    admin = _create_admin_user("admin@example.com")
    db.session.add_all([user, other])
    db.session.commit()

    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    db.session.add(token)
    db.session.commit()

    # Owner can write
    assert token._can_write(user) is True
    # Others cannot (even admin)
    assert token._can_write(other) is False
    assert token._can_write(admin) is False


def test_token_create_permissions_soft_deleted_user(app: Flask, db_session: None) -> None:
    """Test token creation blocked for soft-deleted users."""
    user: CustomUser = CustomUser(email="user@example.com")
    admin = _create_admin_user("admin@example.com")
    db.session.add(user)
    db.session.commit()

    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))

    # Active user can create
    assert token._can_create(user) is True

    # Soft delete user
    user.soft_delete()
    db.session.commit()

    # Soft-deleted user cannot create tokens
    assert token._can_create(user) is False
    # But admin can
    assert token._can_create(admin) is True


def test_setting_permissions_sensitive_flag(app: Flask, db_session: None) -> None:
    """Test setting read permissions based on is_sensitive flag."""
    regular_user: CustomUser = CustomUser(email="regular@example.com", is_premium=False)
    premium_user: CustomUser = CustomUser(email="premium@example.com", is_premium=True)
    admin_user = _create_admin_user("admin@example.com")
    db.session.add_all([regular_user, premium_user])
    db.session.commit()

    normal_setting: CustomUserSetting = CustomUserSetting(
        user_id=regular_user.id, key="theme", value="dark", is_sensitive=False
    )
    sensitive_setting: CustomUserSetting = CustomUserSetting(
        user_id=regular_user.id, key="api_key", value="secret", is_sensitive=True
    )
    db.session.add_all([normal_setting, sensitive_setting])
    db.session.commit()

    # Regular user can read normal setting
    assert normal_setting._can_read(regular_user) is True
    # But cannot read sensitive setting without premium
    assert sensitive_setting._can_read(regular_user) is False

    # Premium user can read sensitive settings
    sensitive_setting_premium: CustomUserSetting = CustomUserSetting(
        user_id=premium_user.id, key="api_key", value="secret", is_sensitive=True
    )
    db.session.add(sensitive_setting_premium)
    db.session.commit()
    assert sensitive_setting_premium._can_read(premium_user) is True

    # Admin can read sensitive settings
    assert sensitive_setting._can_read(admin_user) is True


def test_setting_permissions_system_flag(app: Flask, db_session: None) -> None:
    """Test setting write permissions based on is_system flag."""
    user: CustomUser = CustomUser(email="user@example.com")
    admin = _create_admin_user("admin@example.com")
    superadmin = _create_superadmin_user("super@example.com")
    db.session.add(user)
    db.session.commit()

    normal_setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark", is_system=False)
    system_setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="quota", value="100", is_system=True)
    db.session.add_all([normal_setting, system_setting])
    db.session.commit()

    # User can write normal settings
    assert normal_setting._can_write(user) is True
    # But cannot write system settings
    assert system_setting._can_write(user) is False
    # Admin cannot write system settings
    assert system_setting._can_write(admin) is False
    # Only superadmin can write system settings
    assert system_setting._can_write(superadmin) is True


def test_setting_create_permissions_system_flag(app: Flask, db_session: None) -> None:
    """Test setting creation permissions for system settings."""
    user: CustomUser = CustomUser(email="user@example.com")
    admin = _create_admin_user("admin@example.com")
    superadmin = _create_superadmin_user("super@example.com")
    db.session.add(user)
    db.session.commit()

    normal_setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark")
    system_setting: CustomUserSetting = CustomUserSetting(
        user_id=user.id, key="system_quota", value="100", is_system=True
    )

    # User can create normal settings
    assert normal_setting._can_create(user) is True
    # But cannot create system settings
    assert system_setting._can_create(user) is False
    # Admin cannot create system settings
    assert system_setting._can_create(admin) is False
    # Superadmin can create system settings
    assert system_setting._can_create(superadmin) is True


def test_mixin_functionality_timestamp(app: Flask, db_session: None) -> None:
    """Test TimestampMixin fields are present and functional."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    # TimestampMixin fields exist
    assert hasattr(user, "last_login_at")
    assert hasattr(user, "email_verified_at")
    assert user.last_login_at is None
    assert user.email_verified_at is None


def test_mixin_functionality_profile(app: Flask, db_session: None) -> None:
    """Test ProfileMixin fields and full_name property."""
    user: CustomUser = CustomUser(email="user@example.com", first_name="Jane", last_name="Smith", display_name="JS")
    db.session.add(user)
    db.session.commit()

    # ProfileMixin fields work
    assert user.first_name == "Jane"
    assert user.last_name == "Smith"
    assert user.full_name == "Jane Smith"
    assert user.display_name == "JS"


def test_mixin_functionality_soft_delete(app: Flask, db_session: None) -> None:
    """Test SoftDeleteMixin functionality."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    # Initially not deleted
    assert user.is_deleted is False
    assert user.deleted_at is None

    # Soft delete
    user.soft_delete()
    db.session.commit()
    assert user.is_deleted is True
    assert user.deleted_at is not None  # type: ignore[unreachable]
    assert user.is_enabled is False

    # Restore
    user.restore()
    db.session.commit()
    assert user.is_deleted is False
    assert user.deleted_at is None
    assert user.is_enabled is True


# ============================================================================
# Cascade Delete Tests
# ============================================================================


def test_fully_extended_hard_delete_cascades(app: Flask, db_session: None) -> None:
    """Test that hard delete cascades to roles, tokens, and settings."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="main", display_name="Main", active=True, slug="main")
    db.session.add(domain)
    db.session.flush()

    role: CustomUserRole = CustomUserRole(user_id=user.id, domain_id=domain.id, role=CustomUserRoleEnum.USER)
    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark")

    db.session.add_all([role, token, setting])
    db.session.commit()

    # Hard delete the user (bypass permission checks for testing cascade behavior)
    with CustomUser.bypass_perms():
        user.delete(commit=True)

    # All related records should be cascade deleted
    assert db.session.query(CustomUserRole).count() == 0
    assert db.session.query(CustomToken).count() == 0
    assert db.session.query(CustomUserSetting).count() == 0


def test_fully_extended_soft_delete_no_cascade(app: Flask, db_session: None) -> None:
    """Test that soft delete does NOT cascade to related models."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    domain: CustomDomain = CustomDomain(name="main", display_name="Main", active=True, slug="main")
    db.session.add(domain)
    db.session.flush()

    role: CustomUserRole = CustomUserRole(user_id=user.id, domain_id=domain.id, role=CustomUserRoleEnum.USER)
    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark")

    db.session.add_all([role, token, setting])
    db.session.commit()

    # Soft delete the user
    user.soft_delete()
    db.session.commit()

    # User should be marked as deleted
    assert user.is_deleted is True
    assert user.deleted_at is not None
    assert user.is_enabled is False

    # Related records should NOT be cascade deleted (soft delete doesn't cascade)
    assert db.session.query(CustomUserRole).count() == 1
    assert db.session.query(CustomToken).count() == 1
    assert db.session.query(CustomUserSetting).count() == 1


def test_fully_extended_hard_delete_after_soft_delete(app: Flask, db_session: None) -> None:
    """Test that hard delete cascades even after soft delete."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    role: CustomUserRole = CustomUserRole(user_id=user.id, role=CustomUserRoleEnum.USER)
    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    db.session.add_all([role, token])
    db.session.commit()

    # Soft delete first
    user.soft_delete()
    db.session.commit()
    assert user.is_deleted is True

    # Then hard delete (should cascade)
    with CustomUser.bypass_perms():
        user.delete(commit=True)

    # All related records should be cascade deleted
    assert db.session.query(CustomUserRole).count() == 0
    assert db.session.query(CustomToken).count() == 0


def test_fully_extended_restore_keeps_related_models(app: Flask, db_session: None) -> None:
    """Test that restoring user keeps related models intact."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    setting: CustomUserSetting = CustomUserSetting(user_id=user.id, key="theme", value="dark")
    db.session.add_all([token, setting])
    db.session.commit()

    token_id = token.id
    setting_id = setting.id

    # Soft delete the user
    user.soft_delete()
    db.session.commit()
    assert user.is_deleted is True

    # Restore the user
    user.restore()
    db.session.commit()
    assert user.is_deleted is False
    assert user.deleted_at is None  # type: ignore[unreachable]
    assert user.is_enabled is True

    # Related models should still exist
    assert db.session.get(CustomToken, token_id) is not None
    assert db.session.get(CustomUserSetting, setting_id) is not None


def test_fully_extended_hard_delete_after_restore(app: Flask, db_session: None) -> None:
    """Test that hard delete cascades after restore."""
    user: CustomUser = CustomUser(email="user@example.com")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    token: CustomToken = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
    db.session.add(token)
    db.session.commit()

    # Soft delete and restore
    user.soft_delete()
    db.session.commit()
    assert user.is_deleted is True

    user.restore()
    db.session.commit()
    assert user.is_deleted is False

    # Hard delete should still cascade
    with CustomUser.bypass_perms():  # type: ignore[unreachable]
        user.delete(commit=True)
    assert db.session.query(CustomToken).count() == 0


def test_fully_extended_user_typed(app: Flask, db_session: None) -> None:
    """Test current user retrieval with proper typing."""
    user: CustomUser = CustomUser(email="cara@example.com", bio="Bio")
    user.set_password("secret")
    db.session.add(user)
    db.session.commit()

    token: str = create_access_token(identity=str(user.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        current: CustomUser | None = CustomUser.get_current_user()
        assert current is not None
        assert current.id == user.id


def test_fully_extended_permissions_with_owner(app: Flask, db_session: None) -> None:
    """Test owner-based permissions using can_read/can_write."""
    owner: CustomUser = CustomUser(email="owner@example.com")
    owner.set_password("secret")
    db.session.add(owner)
    db.session.commit()

    token: CustomToken = CustomToken(user_id=owner.id, token=str(uuid.uuid4()), label="owner")
    setting: CustomUserSetting = CustomUserSetting(user_id=owner.id, key="theme", value="dark", scope="user")
    db.session.add_all([token, setting])
    db.session.commit()

    token_id: uuid.UUID | None = token.id
    setting_id: uuid.UUID | None = setting.id
    jwt_token: str = create_access_token(identity=str(owner.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {jwt_token}"}):
        bound_token: CustomToken | None = db.session.get(CustomToken, token_id)
        bound_setting: CustomUserSetting | None = db.session.get(CustomUserSetting, setting_id)
        assert bound_token is not None
        assert bound_setting is not None
        assert bound_token.can_read() is True
        assert bound_token.can_write() is True
        assert bound_setting.can_read() is True
        assert bound_setting.can_write() is True


def test_init_fms_rejects_model_mismatch() -> None:
    """Test that init_fms rejects model mismatches."""
    clear_registration()

    class OtherUser(AbstractUser):
        __abstract__ = True

    init_fms(
        user=CustomUser,
        role=CustomUserRole,
        token=CustomToken,
        domain=CustomDomain,
        setting=CustomUserSetting,
    )

    with pytest.raises(RuntimeError):
        init_fms(user=OtherUser)


def test_fully_extended_type_helpers() -> None:
    """Test type helper functions."""
    init_fms(
        user=CustomUser,
        role=CustomUserRole,
        token=CustomToken,
        domain=CustomDomain,
        setting=CustomUserSetting,
    )

    assert expect_user_model(CustomUser) is CustomUser
    assert expect_role_model(CustomUserRole) is CustomUserRole
    assert expect_token_model(CustomToken) is CustomToken
    assert expect_domain_model(CustomDomain) is CustomDomain
    assert expect_setting_model(CustomUserSetting) is CustomUserSetting

    user: CustomUser | None = CustomUser.get_current_user()
    if user is not None:
        assert isinstance(user.bio, str | None)

    if TYPE_CHECKING:
        assert_type(cast(type[CustomUser], expect_user_model(CustomUser)), type[CustomUser])
        assert_type(cast(type[CustomUserRole], expect_role_model(CustomUserRole)), type[CustomUserRole])
        assert_type(cast(type[CustomToken], expect_token_model(CustomToken)), type[CustomToken])
        assert_type(cast(type[CustomDomain], expect_domain_model(CustomDomain)), type[CustomDomain])
        assert_type(cast(type[CustomUserSetting], expect_setting_model(CustomUserSetting)), type[CustomUserSetting])


def test_permission_enforcement_with_forbidden_errors(app: Flask, db_session: None) -> None:
    """Test that permission violations raise ForbiddenError."""
    user: CustomUser = CustomUser(email="user@example.com")
    other: CustomUser = CustomUser(email="other@example.com")
    db.session.add_all([user, other])
    db.session.commit()

    # Create token for other user
    token: CustomToken = CustomToken(user_id=other.id, token=str(uuid.uuid4()))
    db.session.add(token)
    db.session.commit()

    token_id = token.id
    jwt_token: str = create_access_token(identity=str(user.id))

    with app.test_request_context(headers={"Authorization": f"Bearer {jwt_token}"}):
        bound_token: CustomToken | None = db.session.get(CustomToken, token_id)
        assert bound_token is not None

        # User cannot read other's token
        assert bound_token.can_read() is False

        # Attempting to save should raise ForbiddenError
        with pytest.raises(ForbiddenError):
            bound_token.save()
