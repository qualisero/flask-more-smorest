"""Integration test: demoapp-style FMS integration (custom models + blueprint).

Tests the complete feature set used by demoapp in its integration with flask-more-smorest.
This includes custom user models with mixins, UserBlueprint with custom validation,
nested blueprints, admin roles, domain access, soft delete, profile management,
password recovery, invites, and health endpoints.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
import sqlalchemy as sa
from flask import Flask
from flask.views import MethodView
from flask_jwt_extended import create_access_token, decode_token
from marshmallow import Schema, fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import (
    Api,
    BasePermsModel,
    CRUDBlueprint,
    CRUDMethod,
    db,
    init_db,
    init_jwt,
)
from flask_more_smorest.error import ForbiddenError, UnauthorizedError
from flask_more_smorest.error.error_handlers import RequestHandlers
from flask_more_smorest.perms import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    UserBlueprint,
    clear_registration,
    get_current_user,
    init_fms,
)
from flask_more_smorest.perms.model_mixins import ProfileMixin, SoftDeleteMixin
from flask_more_smorest.perms.models.abstract_role import AbstractDomain, AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser

# ============================================================================
# SHARED SCHEMAS
# ============================================================================


class LoginArgsSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)
    domain = fields.String(required=False)


class TokenLoginArgsSchema(Schema):
    token = fields.String(required=True)
    domain = fields.String(required=False)


class TokenSchema(Schema):
    access_token = fields.String(required=True)
    token_type = fields.String(dump_default="bearer")


class UserSettingsSchema(Schema):
    key = fields.String(required=True)
    value = fields.String(required=False)


class ProfilePicUpdateSchema(Schema):
    profile_pic_id = fields.UUID(allow_none=True, required=False)


class ResetPasswordArgsSchema(Schema):
    email = fields.Email(required=True)
    first_name = fields.String(required=True)
    recovery_url = fields.String(required=False)


class UserRecoveryArgsSchema(Schema):
    new_password = fields.String(required=True)
    recovery_token = fields.String(required=True)


class InviteInputSchema(Schema):
    recipient_email = fields.Email(required=True)
    recipient_user_id = fields.UUID(allow_none=True, required=False)
    token = fields.String(allow_none=True, required=False)
    token_used = fields.Boolean(load_default=False)


# ============================================================================
# SHARED USER BLUEPRINT WITH LOGIN
# ============================================================================


class SharedUserBlueprint(UserBlueprint):
    """Shared UserBlueprint with login endpoint for all tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.me_schema = kwargs.pop("me_schema", None)
        super().__init__(*args, **kwargs)

    def _validate_login(self, user: CustomUser | None, data: dict) -> None:
        """Validate domain access if domain provided."""
        if domain_name := data.get("domain"):
            domain = CustomDomain.get_by_or_404(name=domain_name)
            if not user or not user.has_domain_access(domain.id):
                raise UnauthorizedError("No domain access")

    def _register_login_endpoint(self) -> None:
        @self.public_endpoint
        @self.route("/login/", methods=["POST"])
        @self.arguments(LoginArgsSchema)
        @self.response(200, TokenSchema)
        def login(data: dict[str, Any]) -> dict[str, str]:
            """Login endpoint with optional domain validation."""
            with CustomUser.bypass_perms():
                user = CustomUser.get_by(email=data["email"])

            if not user or not user.is_password_correct(data["password"]):
                raise UnauthorizedError("Invalid email or password")
            if not user.is_enabled:
                raise UnauthorizedError("Account disabled")

            self._validate_login(user, data)
            access_token = create_access_token(identity=user.id)
            return {"access_token": access_token, "token_type": "bearer"}

    def _register_current_user_endpoint(self) -> None:
        """Register /me endpoint if schema is provided."""
        if self.me_schema is None:
            return

        @self.route("/me", methods=["GET"])
        @self.response(200, self.me_schema)
        def get_current_user_profile() -> CustomUser:
            """Get current user profile."""
            user = CustomUser.get_current_user()
            if not user or not user.id:
                raise UnauthorizedError("Not authenticated")
            return user


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

if TYPE_CHECKING:
    CustomProfilePic = Any
    CustomInvite = Any
    CustomDomain = AbstractDomain
    CustomUser = AbstractUser
    CustomUserRole = AbstractUserRole
    CustomToken = AbstractToken
    CustomUserSetting = AbstractUserSetting
    UserSchema = SQLAlchemyAutoSchema
else:
    # At runtime, these are None and will be set by custom_models fixture
    CustomProfilePic = cast(Any, None)
    CustomInvite = cast(Any, None)
    CustomDomain = cast(Any, None)
    CustomUser = cast(Any, None)
    CustomUserRole = cast(Any, None)
    CustomToken = cast(Any, None)
    CustomUserSetting = cast(Any, None)
    UserSchema = cast(Any, None)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="module", autouse=True)
def custom_models() -> Iterator[SimpleNamespace]:
    """Create custom models for testing."""
    import sys
    import types

    clear_registration()
    db.metadata.clear()
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomDomain(AbstractDomain):
        __module__ = module_name
        domain_type: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)

        def _can_read(self, current_user: CustomUser | None) -> bool:
            return True

        def _can_write(self, current_user: CustomUser | None) -> bool:
            return current_user is not None

        def _can_create(self, current_user: CustomUser | None) -> bool:
            return current_user is not None

    class CustomProfilePic(BasePermsModel):
        """Profile picture model (demoapp-specific)."""

        __module__ = module_name
        __tablename__ = "profile_pic"

        filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
        file_size: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
        mime_type: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
        description: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

        def _can_read(self, current_user: CustomUser | None) -> bool:
            return True

        def _can_write(self, current_user: CustomUser | None) -> bool:
            return True

        def _can_create(self, current_user: CustomUser | None) -> bool:
            return True

    class CustomUser(AbstractUser, ProfileMixin, SoftDeleteMixin):
        __module__ = module_name
        profile_pic_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)

        @property
        def profile_pic(self) -> CustomProfilePic | None:
            """Get profile picture by ID."""
            from sqlalchemy.orm import aliased

            pic_alias = aliased(CustomProfilePic)
            return db.session.query(pic_alias).filter(pic_alias.id == self.profile_pic_id).first()

        def has_domain_access(self, domain_id: uuid.UUID | None) -> bool:
            if domain_id is None:
                return True
            return any(role.domain_id == domain_id or role.domain_id is None for role in self.roles)

    class CustomUserRole(AbstractUserRole):
        __module__ = module_name
        pass

    class CustomToken(AbstractToken):
        __module__ = module_name
        pass

    class CustomUserSetting(AbstractUserSetting):
        __module__ = module_name
        pass

    class CustomInvite(BasePermsModel):
        """Account invites - demoapp-specific model."""

        __module__ = module_name
        __tablename__ = "invite"

        recipient_user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True), sa.ForeignKey("user.id"), nullable=True
        )
        recipient_email: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
        sender_user_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True), sa.ForeignKey("user.id"), nullable=False
        )
        token: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
        token_used: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)

        def _can_read(self, current_user: CustomUser | None) -> bool:
            if not current_user:
                return False
            return current_user.id == self.sender_user_id or current_user.is_admin

        def _can_write(self, current_user: CustomUser | None) -> bool:
            if not current_user:
                return False
            return current_user.id == self.sender_user_id or current_user.is_admin

    models = SimpleNamespace(
        CustomProfilePic=CustomProfilePic,
        CustomDomain=CustomDomain,
        CustomUser=CustomUser,
        CustomUserRole=CustomUserRole,
        CustomToken=CustomToken,
        CustomUserSetting=CustomUserSetting,
        CustomInvite=CustomInvite,
    )
    globals().update(models.__dict__)

    try:
        yield models
    finally:
        sys.modules.pop(module_name, None)
        clear_registration()


@pytest.fixture
def app(custom_models: SimpleNamespace) -> Flask:
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "demoapp Integration API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "jwt-secret"

    init_fms(
        user=CustomUser,
        role=CustomUserRole,
        token=CustomToken,
        domain=CustomDomain,
        setting=CustomUserSetting,
    )
    init_db(app)
    init_jwt(app)

    RequestHandlers(app)

    return app


@pytest.fixture
def api(app: Flask) -> Api:
    """Create Api instance for testing."""
    return Api(app)


# ============================================================================
# TESTS - Added one by one
# ============================================================================


def test_1_basic_login_with_shared_blueprint(app: Flask, api: Api) -> None:
    """Test that the shared UserBlueprint with login works."""

    # Define UserSchema for this test
    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True
            include_fk = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        user = CustomUser(email="test@example.com", first_name="Test", last_name="User")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

    client = app.test_client()

    # Test login
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.get_json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_2_soft_delete_feature(app: Flask, api: Api) -> None:
    """Test SoftDeleteMixin functionality used by demoapp."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class RoleSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUserRole
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.GET: {},
            CRUDMethod.POST: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.DELETE: {},
        },
    )

    role_bp = CRUDBlueprint(
        "user_role",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=CustomUserRole,
        schema=RoleSchema,
        methods=[CRUDMethod.POST],
    )
    user_bp.register_blueprint(role_bp)

    # Admin-only soft delete endpoint
    @user_bp.route("<uuid:user_id>/soft-delete", methods=["POST"])
    @user_bp.response(200, UserSchema)
    def soft_delete_user(user_id: uuid.UUID) -> CustomUser:
        """Soft delete a user (admin only)."""
        current = get_current_user()
        if not current or not current.is_admin:
            raise ForbiddenError("Admin only")
        user = CustomUser.get_or_404(user_id)
        user.soft_delete()
        user.save()
        return user

    # Admin-only restore endpoint
    @user_bp.route("<uuid:user_id>/restore", methods=["POST"])
    @user_bp.response(200, UserSchema)
    def restore_user(user_id: uuid.UUID) -> CustomUser:
        """Restore a soft-deleted user (admin only)."""
        current = get_current_user()
        if not current or not current.is_admin:
            raise ForbiddenError("Admin only")
        user = CustomUser.get_or_404(user_id)
        user.restore()
        user.save()
        return user

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        # Create admin user
        admin = CustomUser(email="admin@example.com", first_name="Admin", last_name="User")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()

        # Create regular user
        user = CustomUser(email="user@example.com", first_name="John", last_name="Doe")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        # Make admin an admin
        admin_role = CustomUserRole(user_id=admin.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.flush()

        # Save ID before commit
        user_id = user.id
        db.session.commit()

    client = app.test_client()

    # Login as admin
    admin_login = client.post(
        "/api/user/login/",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["access_token"]

    # Verify admin can access endpoints
    admin_me = client.get(
        "/api/user/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_me.status_code == 200

    # Get user before soft delete
    user_before = client.get(
        f"/api/user/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert user_before.status_code == 200
    user_before_data = user_before.get_json()
    assert user_before_data.get("deleted_at") is None

    # Soft delete the user via API
    soft_delete_resp = client.post(
        f"/api/user/{user_id}/soft-delete",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert soft_delete_resp.status_code == 200
    soft_deleted_user = soft_delete_resp.get_json()
    assert soft_deleted_user.get("deleted_at") is not None

    # Verify soft deleted state via API
    user_after = client.get(
        f"/api/user/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert user_after.status_code == 200
    user_after_data = user_after.get_json()
    assert user_after_data.get("deleted_at") is not None

    # Restore the user via API
    restore_resp = client.post(
        f"/api/user/{user_id}/restore",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert restore_resp.status_code == 200
    restored_user = restore_resp.get_json()
    assert restored_user.get("deleted_at") is None

    # Verify restored user can login
    restored_login = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert restored_login.status_code == 200


def test_3_profile_mixin_and_display_name(app: Flask, api: Api) -> None:
    """Test ProfileMixin and custom display_name property used by demoapp."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True
            include_fk = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        # Create a profile picture
        profile_pic = CustomProfilePic(  # pyright: ignore[reportCallIssue]
            filename="profile.jpg", file_size=12345, mime_type="image/jpeg", description="Test profile picture"
        )
        db.session.add(profile_pic)
        db.session.flush()

        # Test full_name property from ProfileMixin
        user1 = CustomUser(email="test@example.com", first_name="John", last_name="Doe")
        user1.set_password("password123")
        assert user1.full_name == "John Doe"

        user2 = CustomUser(email="test2@example.com", first_name="Jane")
        user2.set_password("password123")
        assert user2.full_name == "Jane"

        user3 = CustomUser(email="test3@example.com", last_name="Smith")
        user3.set_password("password123")
        assert user3.full_name == "Smith"

        user4 = CustomUser(email="test4@example.com")
        user4.set_password("password123")
        assert user4.full_name == ""

        # Test ProfileMixin parse_full_name utility classmethod
        parsed = ProfileMixin.parse_full_name("Alice Wonderland")
        assert parsed["first_name"] == "Alice"
        assert parsed["last_name"] == "Wonderland"

        parsed_single = ProfileMixin.parse_full_name("Bob")
        assert parsed_single["first_name"] == "Bob"
        assert parsed_single["last_name"] == ""

        # Test custom profile_pic_id field (demoapp-specific, NOT from ProfileMixin)
        user1.profile_pic_id = profile_pic.id
        assert user1.profile_pic_id == profile_pic.id

        db.session.add_all([user1, user2, user3, user4])
        db.session.commit()

        user1_id = user1.id

    client = app.test_client()

    # Login and verify profile fields in response
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.get_json()["access_token"]

    me_resp = client.get(f"/api/user/{user1_id}", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    user_data = me_resp.get_json()
    assert user_data["first_name"] == "John"
    assert user_data["last_name"] == "Doe"


def test_4_password_recovery_flow(app: Flask, api: Api) -> None:
    """Test password recovery endpoints used by demoapp."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.POST: {"admin_only": True, "schema": UserSchema}},
    )

    # Send recovery token endpoint
    @user_bp.public_endpoint
    @user_bp.route("/send_recovery_token", methods=["POST"])
    @user_bp.arguments(ResetPasswordArgsSchema)
    @user_bp.response(200, description="Password reset email sent")
    @user_bp.alt_response(401, description="Wrong email or first name")
    def send_recovery_token(payload: dict[str, str]):
        with CustomUser.bypass_perms():
            user = CustomUser.get_by(email=payload["email"])
        if not user or payload["first_name"].lower() != (user.first_name or "").lower():
            raise UnauthorizedError("Wrong email or first name")

        # In real implementation, send email with token
        token = create_access_token(identity=user.id, expires_delta=dt.timedelta(seconds=3600 * 2))
        return {"debug_recovery_token": token}

    # Reset password endpoint
    @user_bp.public_endpoint
    @user_bp.route("reset_password", methods=["POST"])
    @user_bp.arguments(UserRecoveryArgsSchema)
    @user_bp.response(200, TokenSchema)
    @user_bp.alt_response(401, description="Invalid token")
    def reset_password(payload: dict[str, str]):
        try:
            token_contents = decode_token(payload["recovery_token"])
            recover_id = token_contents["sub"]
        except Exception:
            raise UnauthorizedError("Invalid token")

        with CustomUser.bypass_perms():
            user = CustomUser.get_or_404(recover_id)
            user.set_password(payload["new_password"])
            user.save()

        access_token = create_access_token(identity=user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        user = CustomUser(email="test@example.com", first_name="John", last_name="Doe")
        user.set_password("oldpassword")
        db.session.add(user)
        db.session.flush()
        user_id = user.id
        db.session.commit()

    client = app.test_client()

    # Test old password works
    old_login = client.post(
        "/api/user/login/",
        json={"email": "test@example.com", "password": "oldpassword"},
    )
    assert old_login.status_code == 200

    # Send recovery token with wrong first name - should fail
    bad_recovery = client.post(
        "/api/user/send_recovery_token",
        json={"email": "test@example.com", "first_name": "Wrong"},
    )
    assert bad_recovery.status_code == 401

    # Send recovery token with correct info
    recovery_resp = client.post(
        "/api/user/send_recovery_token",
        json={"email": "test@example.com", "first_name": "John"},
    )
    assert recovery_resp.status_code == 200
    recovery_data = recovery_resp.get_json()
    recovery_token = recovery_data["debug_recovery_token"]

    # Reset password
    reset_resp = client.post(
        "/api/user/reset_password",
        json={"new_password": "newpassword123", "recovery_token": recovery_token},
    )
    assert reset_resp.status_code == 200
    reset_token = reset_resp.get_json()["access_token"]

    # Verify user ID is still valid after reset via API
    me_after_reset = client.get(
        "/api/user/me",
        headers={"Authorization": f"Bearer {reset_token}"},
    )
    assert me_after_reset.status_code == 200
    me_data = me_after_reset.get_json()
    assert uuid.UUID(me_data["id"]) == user_id

    # Old password should no longer work
    old_login_fail = client.post(
        "/api/user/login/",
        json={"email": "test@example.com", "password": "oldpassword"},
    )
    assert old_login_fail.status_code == 401

    # New password should work
    new_login = client.post(
        "/api/user/login/",
        json={"email": "test@example.com", "password": "newpassword123"},
    )
    assert new_login.status_code == 200


def test_5_invite_system(app: Flask, api: Api) -> None:
    """Test invite creation and listing (demoapp-specific model)."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class InviteSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomInvite
            load_instance = False  # Return dict, not instance
            include_fk = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.POST: {"admin_only": True, "schema": UserSchema}},
    )

    # Invite endpoints
    @user_bp.route("<uuid:user_id>/invite/", methods=["POST", "GET"])
    class InviteEndpoint(MethodView):
        @user_bp.arguments(InviteInputSchema)  # Use input schema (sender_user_id is set programmatically)
        @user_bp.response(200, InviteSchema)  # Use output schema for response
        def post(self, payload, user_id):
            """Create an invite."""
            # Verify sender has permission
            current = get_current_user()
            if not current or (current.id != user_id and not current.is_admin):
                raise ForbiddenError("Not allowed to send invites")
            payload["sender_user_id"] = user_id  # Set sender from route parameter
            invite = CustomInvite(**payload)  # pyright: ignore[reportCallIssue]
            invite.save()
            return invite

        @user_bp.response(200, InviteSchema(many=True))
        def get(self, user_id):
            """List invites sent by user."""
            current = get_current_user()
            if not current or (current.id != user_id and not current.is_admin):
                raise ForbiddenError("Not allowed to view invites")
            return CustomInvite.query.filter_by(sender_user_id=user_id).all()

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        sender = CustomUser(email="sender@example.com")
        sender.set_password("password123")
        db.session.add(sender)
        db.session.flush()

        recipient = CustomUser(email="recipient@example.com")
        recipient.set_password("password123")
        db.session.add(recipient)
        db.session.flush()

        # Make sender an admin
        admin_role = CustomUserRole(user_id=sender.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

        sender_id = sender.id
        recipient_id = recipient.id

    client = app.test_client()

    # Login as sender
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "sender@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    sender_token = login_resp.get_json()["access_token"]

    # Create invite
    create_resp = client.post(
        f"/api/user/{sender_id}/invite/",
        json={
            "recipient_email": "newuser@example.com",
            "recipient_user_id": str(recipient_id),
        },
        headers={"Authorization": f"Bearer {sender_token}"},
    )
    assert create_resp.status_code == 200
    invite_data = create_resp.get_json()
    assert invite_data["recipient_email"] == "newuser@example.com"
    # Verify invite has valid ID from response
    assert "id" in invite_data
    # invite_id = uuid.UUID(invite_data["id"])

    # List invites
    list_resp = client.get(
        f"/api/user/{sender_id}/invite/",
        headers={"Authorization": f"Bearer {sender_token}"},
    )
    assert list_resp.status_code == 200
    invites = list_resp.get_json()
    assert len(invites) == 1
    assert invites[0]["recipient_email"] == "newuser@example.com"


def test_6_admin_role_enforcement(app: Flask, api: Api) -> None:
    """Test admin role properties and enforcement."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class RoleSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUserRole
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.POST: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.GET: {},
        },
    )

    role_bp = CRUDBlueprint(
        "user_role",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=CustomUserRole,
        schema=RoleSchema,
        methods=[CRUDMethod.POST, CRUDMethod.INDEX],
    )
    user_bp.register_blueprint(role_bp)

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        # Create admin user
        admin = CustomUser(email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()

        # Create superadmin user
        superadmin = CustomUser(email="superadmin@example.com")
        superadmin.set_password("super123")
        db.session.add(superadmin)
        db.session.flush()

        # Create regular user
        regular = CustomUser(email="user@example.com")
        regular.set_password("user123")
        db.session.add(regular)
        db.session.flush()

        # Assign roles
        admin_role = CustomUserRole(user_id=admin.id, role=ROLE_ADMIN)
        super_role = CustomUserRole(user_id=superadmin.id, role=ROLE_SUPERADMIN)
        db.session.add_all([admin_role, super_role])
        db.session.commit()

        admin_id = admin.id
        super_id = superadmin.id
        user_id = regular.id

    client = app.test_client()

    # Verify admin can access INDEX endpoint
    admin_login = client.post(
        "/api/user/login/",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["access_token"]

    index_resp = client.get("/api/user/", headers={"Authorization": f"Bearer {admin_token}"})
    assert index_resp.status_code == 200
    users = index_resp.get_json()
    assert len(users) == 3

    # Verify regular user cannot access INDEX endpoint
    user_login = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "user123"},
    )
    assert user_login.status_code == 200
    user_token = user_login.get_json()["access_token"]

    user_index_resp = client.get("/api/user/", headers={"Authorization": f"Bearer {user_token}"})
    assert user_index_resp.status_code == 403

    # Test role assignment and querying
    with app.app_context():
        with CustomUser.bypass_perms():
            admin_user = CustomUser.get_or_404(admin_id)
            assert admin_user.is_admin
            assert not admin_user.is_superadmin

            super_user = CustomUser.get_or_404(super_id)
            assert super_user.is_superadmin
            # Superadmin is also an admin
            assert super_user.is_admin

            regular_user = CustomUser.get_or_404(user_id)
            assert not regular_user.is_admin
            assert not regular_user.is_superadmin


def test_7_bypass_perms_context(app: Flask, api: Api) -> None:
    """Test bypass_perms context manager for admin operations."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    # Admin-only delete endpoint using bypass_perms
    @user_bp.route("<uuid:user_id>/admin-delete", methods=["DELETE"])
    @user_bp.response(204)
    def admin_delete(user_id: uuid.UUID):
        current = get_current_user()
        if not current or not current.is_admin:
            raise ForbiddenError("Admin only")

        # Use bypass_perms to delete user regardless of permissions
        with CustomUser.bypass_perms():
            user = CustomUser.get_or_404(user_id)
            user.delete()

        return "", 204

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        # Create admin and regular user
        admin = CustomUser(email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()

        user = CustomUser(email="user@example.com")
        user.set_password("user123")
        db.session.add(user)
        db.session.flush()

        admin_role = CustomUserRole(user_id=admin.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

        admin_id = admin.id
        user_id = user.id

    client = app.test_client()

    # Login as admin
    admin_login = client.post(
        "/api/user/login/",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["access_token"]

    # Verify admin has correct ID
    with app.app_context():
        with CustomUser.bypass_perms():
            retrieved_admin = CustomUser.get_by(email="admin@example.com")
            assert retrieved_admin is not None
            assert retrieved_admin.id == admin_id

    # Admin can delete user using bypass_perms
    delete_resp = client.delete(
        f"/api/user/{user_id}/admin-delete",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_resp.status_code == 204

    # Verify user is deleted
    with app.app_context():
        deleted_user = CustomUser.get_by(id=user_id)
        assert deleted_user is None


def test_8_health_endpoint(app: Flask, api: Api) -> None:
    """Test health endpoint registration and response."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

    client = app.test_client()

    # Test health endpoint
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.get_json()
    assert health_data["status"] == "healthy"
    assert "timestamp" in health_data
    assert "version" in health_data
    assert health_data["database"] == "connected"


def test_9_domain_access_control(app: Flask, api: Api) -> None:
    """Test domain access control with has_domain_access method."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class RoleSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUserRole
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.POST: {"admin_only": True, "schema": UserSchema}, CRUDMethod.GET: {}},
    )

    role_bp = CRUDBlueprint(
        "user_role",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=CustomUserRole,
        schema=RoleSchema,
        methods=[CRUDMethod.POST, CRUDMethod.INDEX],
    )
    user_bp.register_blueprint(role_bp)

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        # Create domains
        domain1 = CustomDomain(name="domain1", display_name="Domain 1", active=True)
        domain2 = CustomDomain(name="domain2", display_name="Domain 2", active=True)
        db.session.add_all([domain1, domain2])
        db.session.flush()

        # Create user with access to domain1 only
        user = CustomUser(email="user@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        # Add role for domain1 only (no global role)
        role1 = CustomUserRole(user_id=user.id, domain_id=domain1.id, role="ADMIN")
        db.session.add(role1)
        db.session.commit()

        user_id = user.id
        d1_id = domain1.id
        d2_id = domain2.id

    client = app.test_client()

    # Test login with domain user has access to
    login_ok = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123", "domain": "domain1"},
    )
    if login_ok.status_code != 200:
        print(f"\nDEBUG: Login failed with status {login_ok.status_code}")
        print(f"DEBUG: Response: {login_ok.get_json()}")
    assert login_ok.status_code == 200

    # Test login with domain user does NOT have access to
    login_fail = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123", "domain": "domain2"},
    )
    assert login_fail.status_code == 401

    # Test login without domain - should succeed (domain check only happens when domain is specified)
    login_no_domain = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123"},
    )
    # Login succeeds - domain access is only validated when domain parameter is provided
    assert login_no_domain.status_code == 200

    # Verify has_domain_access method
    with app.app_context():
        with CustomUser.bypass_perms():
            user = CustomUser.get_or_404(user_id)
            assert user.has_domain_access(d1_id)  # Has direct access
            assert not user.has_domain_access(d2_id)  # No access
            assert user.has_domain_access(None)  # Global access


def test_10_user_crud_operations(app: Flask, api: Api) -> None:
    """Test complete CRUD operations on users."""

    # Define schemas with correct model reference
    class UserOutputSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    # Create a schema that doesn't load instances (for POST input)
    class UserInputSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = False

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserOutputSchema,
        me_schema=UserOutputSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserOutputSchema},
            CRUDMethod.GET: {},
            # Note: We'll use custom endpoint for creation
            CRUDMethod.DELETE: {},
        },
    )

    # Custom POST endpoint to avoid load_instance issues
    @user_bp.route("create", methods=["POST"])
    @user_bp.arguments(UserInputSchema)
    @user_bp.response(200, UserOutputSchema)
    def create_user(data: dict[str, Any]) -> CustomUser:
        """Create a new user."""
        user = CustomUser(**data)
        user.save()
        # Refresh to ensure all fields are loaded before serialization
        db.session.refresh(user)
        return user

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        admin = CustomUser(email="admin@example.com")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()

        admin_role = CustomUserRole(user_id=admin.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

    client = app.test_client()

    # Login as admin
    admin_login = client.post(
        "/api/user/login/",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.get_json()["access_token"]

    # CREATE user via POST
    create_resp = client.post(
        "/api/user/create",
        json={
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200
    new_user_data = create_resp.get_json()
    new_user_id = uuid.UUID(new_user_data["id"])
    assert new_user_data["email"] == "newuser@example.com"

    # READ user via GET
    get_resp = client.get(
        f"/api/user/{new_user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 200
    user_data = get_resp.get_json()
    assert user_data["email"] == "newuser@example.com"

    # INDEX all users
    index_resp = client.get("/api/user/", headers={"Authorization": f"Bearer {admin_token}"})
    assert index_resp.status_code == 200
    users = index_resp.get_json()
    assert len(users) == 2

    # DELETE user
    delete_resp = client.delete(
        f"/api/user/{new_user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_resp.status_code == 204

    # Verify deletion
    get_after_delete = client.get(
        f"/api/user/{new_user_id}/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_after_delete.status_code == 404


def test_11_user_profile_picture_update(app: Flask, api: Api) -> None:
    """Test profile picture upload endpoint used by demoapp."""

    # Create a simple Image model for testing
    class TestImage(BasePermsModel):
        __tablename__ = "test_image"
        id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
        filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
        description: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

        def _can_read(self, current_user):
            return True

        def _can_write(self, current_user):
            return True

        def _can_create(self, current_user):
            return True

    class UserWithProfileSchema(Schema):
        id = fields.UUID(dump_only=True)
        email = fields.Email(dump_only=True)
        profile_pic_id = fields.UUID(allow_none=True)

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserWithProfileSchema,
        methods={CRUDMethod.GET: {}},
    )

    # Profile picture upload endpoint
    @user_bp.route("<uuid:user_id>/profile_pic", methods=["PUT"])
    @user_bp.arguments(ProfilePicUpdateSchema, location="json")
    @user_bp.response(200, UserWithProfileSchema)
    def upload_profile_pic(payload: dict[str, Any], user_id: uuid.UUID):
        """Upload user profile picture."""
        user = CustomUser.get_or_404(user_id)
        old_profile_pic_id = user.profile_pic_id

        # In real demoapp, this would process the actual file upload
        # For testing, we simulate by creating an image record
        img = TestImage(filename="profile.jpg", description="Profile picture")
        db.session.add(img)
        db.session.flush()

        user.profile_pic_id = img.id
        user.save()

        # Delete old profile pic if exists
        if old_profile_pic_id:
            old_img = TestImage.get_by(id=old_profile_pic_id)
            if old_img:
                old_img.delete()

        return user

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        user = CustomUser(email="user@example.com", first_name="John", last_name="Doe")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        admin_role = CustomUserRole(user_id=user.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

        user_id = user.id

    client = app.test_client()

    # Login
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.get_json()["access_token"]

    # Verify profile_pic_id starts as None
    get_before = client.get(f"/api/user/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_before.status_code == 200
    assert get_before.get_json()["profile_pic_id"] is None

    # Update profile picture (send empty JSON, endpoint will create test image)
    upload_resp = client.put(
        f"/api/user/{user_id}/profile_pic",
        json={},  # Empty JSON, endpoint creates test image
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_resp.status_code == 200
    updated_user = upload_resp.get_json()
    assert "profile_pic_id" in updated_user
    assert updated_user["profile_pic_id"] is not None


def test_12_user_patch_update(app: Flask, api: Api) -> None:
    """Test user update via PATCH endpoint used by demoapp."""

    # Define local schemas to avoid cross-test pollution
    class UserOutputSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class UserPrivateSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = False
            exclude = ("roles", "settings", "tokens")

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserOutputSchema,
        me_schema=UserOutputSchema,
        methods={
            CRUDMethod.GET: {},
            CRUDMethod.POST: {"admin_only": True, "schema": UserOutputSchema},
        },
    )

    # PATCH endpoint for user update
    @user_bp.route("<uuid:user_id>", methods=["PATCH"])
    @user_bp.arguments(UserPrivateSchema(partial=True))
    @user_bp.response(200, UserOutputSchema)
    def patch_user(payload: dict[str, Any], user_id: uuid.UUID):
        """Update user if writable."""
        user = CustomUser.get_or_404(user_id)
        user.update(**payload)
        user.save()
        return user

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        user = CustomUser(email="user@example.com", first_name="John", last_name="Doe")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        admin_role = CustomUserRole(user_id=user.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

        user_id = user.id

    client = app.test_client()

    # Login
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.get_json()["access_token"]

    # Get user before patch (need auth to access)
    get_before = client.get(
        f"/api/user/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_before.status_code == 200
    before_data = get_before.get_json()
    if "first_name" not in before_data:
        print(f"\nDEBUG: GET response keys: {list(before_data.keys())}")
        print(f"DEBUG: Response: {before_data}")
    assert before_data.get("first_name") == "John"
    assert before_data.get("last_name") == "Doe"

    # Patch user
    patch_resp = client.patch(
        f"/api/user/{user_id}",
        json={"first_name": "Jane", "last_name": "Smith"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_resp.status_code == 200
    patched_user = patch_resp.get_json()
    assert patched_user["first_name"] == "Jane"
    assert patched_user["last_name"] == "Smith"


def test_13_user_full_details_endpoint(app: Flask, api: Api) -> None:
    """Test GET /full endpoint for private user details."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    class UserPrivateSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True
            exclude = ("roles", "settings", "tokens")

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    # GET /full endpoint with private fields
    @user_bp.route("<uuid:user_id>/full", methods=["GET"])
    @user_bp.response(200, UserPrivateSchema)
    def get_user_full(user_id: uuid.UUID):
        """Get user details with private fields."""
        # In demoapp, this would check permissions
        # For testing, we allow the user to view their own full details
        return CustomUser.get_or_404(user_id)

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        admin = CustomUser(email="admin@example.com", first_name="Admin", last_name="User")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()

        user = CustomUser(email="user@example.com", first_name="John", last_name="Doe")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        admin_role = CustomUserRole(user_id=admin.id, role=ROLE_ADMIN)
        db.session.add(admin_role)
        db.session.commit()

        admin_id = admin.id
        user_id = user.id

    client = app.test_client()

    # Verify admin ID is correctly saved
    with app.app_context():
        with CustomUser.bypass_perms():
            retrieved_admin = CustomUser.get_by(email="admin@example.com")
            assert retrieved_admin is not None
            assert retrieved_admin.id == admin_id

    # Login as user
    user_login = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert user_login.status_code == 200
    user_token = user_login.get_json()["access_token"]

    # User can see their own full details
    full_resp = client.get(
        f"/api/user/{user_id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert full_resp.status_code == 200
    full_user = full_resp.get_json()
    assert full_user["first_name"] == "John"
    assert full_user["last_name"] == "Doe"


def test_14_error_handling_scenarios(app: Flask, api: Api) -> None:
    """Test various error scenarios."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True

    user_bp = SharedUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={CRUDMethod.GET: {}},
    )

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()

        user = CustomUser(email="user@example.com", first_name="John", last_name="Doe")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        admin_role = CustomUserRole(user_id=user.id, role="USER")
        db.session.add(admin_role)
        db.session.commit()

        user_id = user.id

    client = app.test_client()

    # Test invalid password
    bad_password = client.post(
        "/api/user/login/",
        json={"email": "user@example.com", "password": "wrongpassword"},
    )
    assert bad_password.status_code == 401

    # Test non-existent user
    bad_user = client.post(
        "/api/user/login/",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert bad_user.status_code == 401

    # Test accessing user that doesn't exist
    bad_get = client.get(f"/api/user/{uuid.uuid4()}/")
    assert bad_get.status_code == 404

    # Test unauthorized access (no token)
    # Without authentication, returns 401 for unauthenticated access
    unauthorized = client.get(f"/api/user/{user_id}")
    assert unauthorized.status_code == 401


# ============================================================================
# TEST 15: Demoapp-style integration with token login
# ============================================================================


def test_15_demoapp_style_integration(app: Flask, api: Api) -> None:
    """Test demoapp-style integration with token login."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUser
            load_instance = True
            include_fk = True

    class RoleSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUserRole
            load_instance = True
            include_fk = True

    user_bp = SharedUserBlueprint(
        name="user_demoapp",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        me_schema=UserSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.GET: {},
            CRUDMethod.POST: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.DELETE: {},
        },
    )

    role_bp = CRUDBlueprint(
        "user_role_demoapp",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=CustomUserRole,
        schema=RoleSchema,
        methods=[CRUDMethod.INDEX],
    )
    user_bp.register_blueprint(role_bp)

    @user_bp.public_endpoint
    @user_bp.route("token_login", methods=["POST"])
    @user_bp.arguments(TokenLoginArgsSchema)
    @user_bp.response(200, TokenSchema)
    def token_login(data: dict[str, Any]) -> dict[str, str]:
        token = CustomToken.query.filter_by(token=data["token"]).first()
        if not token:
            raise UnauthorizedError("Invalid token")
        if not token.user.is_enabled:
            raise UnauthorizedError("Account disabled")
        if domain_name := data.get("domain"):
            domain = CustomDomain.get_by_or_404(name=domain_name)
            if not token.user.has_domain_access(domain.id):
                raise UnauthorizedError("No domain access")
        access_token = create_access_token(identity=token.user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    @user_bp.route("<uuid:user_id>/settings/", methods=["GET"])
    @user_bp.response(200, UserSettingsSchema(many=True))
    def list_user_settings(user_id: uuid.UUID) -> list[CustomUserSetting]:
        user = CustomUser.get_or_404(user_id)
        if not user.can_write():
            raise UnauthorizedError("Not allowed")
        return CustomUserSetting.query.filter_by(user_id=user_id).all()

    @user_bp.route("<uuid:user_id>/settings/", methods=["POST"])
    @user_bp.arguments(UserSettingsSchema, location="json")
    @user_bp.response(200, UserSettingsSchema(many=True))
    def user_settings(payload: dict[str, Any], user_id: uuid.UUID) -> list[CustomUserSetting]:
        user = CustomUser.get_or_404(user_id)
        if not user.can_write():
            raise UnauthorizedError("Not allowed")
        key = payload["key"]
        setting = CustomUserSetting.get_by(user_id=user_id, key=key)
        if setting:
            setting.value = payload.get("value")
            setting.save()
        else:
            setting = CustomUserSetting(user_id=user_id, key=key, value=payload.get("value"))
            setting.save()
        return CustomUserSetting.query.filter_by(user_id=user_id).all()

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        domain = CustomDomain(name="main", display_name="Main", active=True)
        db.session.add(domain)
        db.session.flush()

        user = CustomUser(email="dave@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.flush()

        role = CustomUserRole(user_id=user.id, domain_id=domain.id, role="ADMIN")
        token_value = str(uuid.uuid4())
        token = CustomToken(user_id=user.id, token=token_value)
        db.session.add_all([role, token])
        db.session.commit()

        # Save user.id for later use after commit
        user_id = user.id

    client = app.test_client()
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "dave@example.com", "password": "secret", "domain": "main"},
    )
    assert login_resp.status_code == 200
    jwt_token = login_resp.get_json()["access_token"]

    me_resp = client.get("/api/user/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert me_resp.status_code == 200

    token_login_resp = client.post(
        "/api/user/token_login",
        json={"token": str(uuid.uuid4()), "domain": "main"},
    )
    assert token_login_resp.status_code == 401

    valid_token_resp = client.post(
        "/api/user/token_login",
        json={"token": token_value, "domain": "main"},
    )
    assert valid_token_resp.status_code == 200

    settings_resp = client.post(
        f"/api/user/{user_id}/settings/",
        json={"key": "theme", "value": "dark"},
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert settings_resp.status_code == 200

    role_resp = client.get(
        f"/api/user/{user_id}/role/",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert role_resp.status_code == 200
