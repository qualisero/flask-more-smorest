Demoapp-Style Integration
============================

Complete example of integrating flask-more-smorest with an existing application's
custom user models, following the pattern used by demoapp.

.. tip::

   Looking to extend the default User model? See :doc:`user-extension` for extension patterns.
   This guide shows complete custom model integration.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

This integration pattern is ideal when you:

- **Have existing user models** - Your app already has User/UserRole/Domain models
- **Need custom permission logic** - Domain-based access, custom validation, etc.
- **Use model mixins** - Profile, soft delete, timestamps, etc.
- **Custom login validation** - Domain checks, additional security layers

The pattern demonstrates:

1. Extending abstract FMS models with custom fields
2. Using mixins (ProfileMixin, SoftDeleteMixin)
3. Custom permission methods (``_can_read``, ``_can_write``, ``_can_create``)
4. Domain-based access control (multi-tenant support)
5. Custom UserBlueprint with login validation hooks
6. Invite system for user registration
7. Password recovery flow

Complete Example
----------------

.. code-block:: python

    import uuid
    import sqlalchemy as sa
    from http import HTTPStatus
    from flask import Flask
    from flask_jwt_extended import create_access_token, decode_token
    from flask_more_smorest import (
        Api,
        CRUDBlueprint,
        CRUDMethod,
        BasePermsModel,
        db,
        init_db,
    )
    from flask_more_smorest.error import UnauthorizedError, ForbiddenError
    from flask_more_smorest.perms import (
        init_fms,
        UserBlueprint,
        ProfileMixin,
        SoftDeleteMixin,
        BaseRoleEnum,
    )
    from flask_more_smorest.perms.models import (
        AbstractDomain,
        AbstractUser,
        AbstractUserRole,
        AbstractToken,
        AbstractUserSetting,
    )
    from marshmallow import Schema, fields
    from sqlalchemy.orm import Mapped, mapped_column

    # -------------------------------------------------------------------------
    # Custom Domain Model (multi-tenant support)
    # -------------------------------------------------------------------------

    class Domain(AbstractDomain):
        """Custom domain model with additional fields."""
        __tablename__ = "domain"

        # Custom fields
        domain_type: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
        lat: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
        lon: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
        area_geojson = db.Column(db.JSON, nullable=True)

        def _can_read(self, current_user):
            """Allow any user to read domains."""
            return True

        def _can_write(self, current_user):
            """Allow only authenticated users to write domains."""
            return current_user is not None

        def _can_create(self, current_user):
            """Allow only authenticated users to create domains."""
            return current_user is not None


    # -------------------------------------------------------------------------
    # Custom User Model with Mixins
    # -------------------------------------------------------------------------

    class User(AbstractUser, ProfileMixin, SoftDeleteMixin):
        """Custom user model with mixins.

        - AbstractUser: Core FMS user functionality (email, password, roles, etc.)
        - ProfileMixin: first_name, last_name, display_name, avatar_url
        - SoftDeleteMixin: deleted_at, is_deleted, soft_delete(), restore()
        """
        __tablename__ = "user"

        # Custom fields
        profile_pic_id: Mapped[uuid.UUID | None] = mapped_column(
            sa.Uuid(as_uuid=True), nullable=True
        )

        # Custom display_name property (overrides ProfileMixin)
        @property
        def display_name(self) -> str:
            """Return dynamically-generated display name."""
            if self.first_name:
                if self.last_name:
                    initials = "".join(w[0] for w in self.last_name.split(" ") if w)
                    return f"{self.first_name} {initials}."
                return self.first_name
            elif self.last_name:
                return self.last_name
            return self.email.split("@")[0] if self.email else ""

        def has_domain_access(self, domain_id: uuid.UUID | None) -> bool:
            """Check if user has access to specified domain."""
            if domain_id is None:
                return True
            return any(
                role.domain_id == domain_id or role.domain_id is None
                for role in self.roles
            )

        def _can_read(self, current_user):
            """Users can read their own profile, admins can read all."""
            if not current_user:
                return False
            return self.id == current_user.id or current_user.is_admin

        def _can_write(self, current_user):
            """Users can edit their own profile."""
            if not current_user:
                return False
            return self.id == current_user.id or current_user.is_admin

        def _can_create(self, current_user):
            """Only admins can create users."""
            if not current_user:
                return False
            return current_user.is_admin


    # -------------------------------------------------------------------------
    # Invite Model (demoapp-specific)
    # -------------------------------------------------------------------------

    class Invite(BasePermsModel):
        """Account invites."""
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

        def _can_read(self, current_user):
            """Sender can read their invites."""
            if not current_user:
                return False
            return current_user.id == self.sender_user_id or current_user.is_admin

        def _can_write(self, current_user):
            """Sender can manage their invites."""
            if not current_user:
                return False
            return current_user.id == self.sender_user_id or current_user.is_admin

    # -------------------------------------------------------------------------
    # Other Models (use FMS defaults)
    # -------------------------------------------------------------------------

    # Use FMS default UserRole, Token, UserSetting models
    # They automatically reference your custom User model
    from flask_more_smorest.perms.models.defaults import UserRole, Token, UserSetting

    # -------------------------------------------------------------------------
    # Custom UserBlueprint with Login Validation
    # -------------------------------------------------------------------------

    class DemoUserBlueprint(UserBlueprint):
        """User blueprint with custom domain validation.

        Overrides ``_validate_login()`` to add domain access checks
        while keeping all other login logic handled by FMS.
        """

        def _validate_login(self, user: User, data: dict) -> None:
            """Validate login with custom domain access check.

            Called by FMS after password verification and is_enabled check.
            Only domain validation needs to be handled here.

            Args:
                user: The user object attempting to login
                data: The login data (email, password, domain)

            Raises:
                UnauthorizedError: If user doesn't have access to specified domain
            """
            if domain_name := data.get("domain"):
                domain = Domain.get_by_or_404(name=domain_name)
                if not user.has_domain_access(domain.id):
                    raise UnauthorizedError("No domain access")

        def _register_current_user_endpoint(self) -> None:
            """Custom /me endpoint with private fields."""
            @self.route("/me", methods=["GET"])
            @self.response(HTTPStatus.OK, UserSchema)
            def get_current_user_profile() -> User:
                user = User.get_current_user()
                if not user or not user.id:
                    raise UnauthorizedError("Not authenticated")
                return user


    # -------------------------------------------------------------------------
    # Schemas
    # -------------------------------------------------------------------------

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


    class UserSchema(Schema):
        """Public user schema."""
        email = fields.Email(required=True)
        is_deleted = fields.Boolean(dump_only=True)
        display_name = fields.String(dump_only=True)
        roles = fields.List(fields.String(), dump_only=True)


    class UserSettingsSchema(Schema):
        key = fields.String(required=True)
        value = fields.String(required=False)


    # -------------------------------------------------------------------------
    # Application Setup
    # -------------------------------------------------------------------------

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="postgresql://user:pass@localhost/db",
        API_TITLE="Demoapp API",
        API_VERSION="v1",
        OPENAPI_VERSION="3.0.2",
        SECRET_KEY="your-secret-key",
        JWT_SECRET_KEY="your-jwt-secret",
        # Health endpoint configuration
        HEALTH_ENDPOINT_ENABLED=True,
        HEALTH_ENDPOINT_PATH="/health",
    )

    # Register all models with FMS
    # Since we're using custom models for User and Domain, we specify those.
    # UserRole, Token, and UserSetting will be auto-loaded as defaults.
    init_fms(user=User, domain=Domain)

    # Initialize database and JWT
    init_db(app)

    # Create API instance (handles JWT, permissions, health endpoint)
    api = Api(app)

    # -------------------------------------------------------------------------
    # Blueprints
    # -------------------------------------------------------------------------

    # User blueprint with custom validation
    user_bp = DemoUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=User,
        schema=UserSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.GET: {},
            CRUDMethod.POST: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.DELETE: {},
        },
    )

    # Role blueprint nested under users
    role_bp = CRUDBlueprint(
        "user_role",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=UserRole,
        schema=UserRole.Schema,
        methods=[CRUDMethod.INDEX, CRUDMethod.POST, CRUDMethod.DELETE],
    )
    user_bp.register_blueprint(role_bp)

    # Token login endpoint (public, uses existing token)
    @user_bp.public_endpoint
    @user_bp.route("token_login", methods=["POST"])
    @user_bp.arguments(TokenLoginArgsSchema)
    @user_bp.response(HTTPStatus.OK, TokenSchema)
    def token_login(data: dict) -> dict[str, str]:
        """Login with existing token."""
        token = Token.query.filter_by(token=data["token"]).first()
        if not token:
            raise UnauthorizedError("Invalid token")
        if not token.user.is_enabled:
            raise UnauthorizedError("Account disabled")

        if domain_name := data.get("domain"):
            domain = Domain.get_by_or_404(name=domain_name)
            if not token.user.has_domain_access(domain.id):
                raise UnauthorizedError("No domain access")

        access_token = create_access_token(identity=token.user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    # User settings endpoints
    @user_bp.route("<uuid:user_id>/settings/", methods=["GET", "POST"])
    class UserSettings(MethodView):
        @user_bp.response(HTTPStatus.OK, UserSettingsSchema(many=True))
        def get(self, user_id: uuid.UUID) -> list:
            """Get user settings."""
            user = User.get_or_404(user_id)
            if not user.can_write():
                raise ForbiddenError("Not allowed")
            return UserSetting.query.filter_by(user_id=user_id).all()

        @user_bp.arguments(UserSettingsSchema, location="json")
        @user_bp.response(HTTPStatus.OK, UserSettingsSchema(many=True))
        def post(self, payload: dict, user_id: uuid.UUID) -> list:
            """Update user settings."""
            user = User.get_or_404(user_id)
            if not user.can_write():
                raise ForbiddenError("Not allowed")
            key = payload["key"]
            setting = UserSetting.get_by(user_id=user_id, key=key)
            if setting:
                setting.value = payload.get("value")
                setting.save()
            else:
                setting = UserSetting(user_id=user_id, key=key, value=payload.get("value"))
                setting.save()
            return UserSetting.query.filter_by(user_id=user_id).all()

    # Invite endpoints
    @user_bp.route("<uuid:user_id>/invite/", methods=["POST", "GET"])
    class InviteEndpoint(MethodView):
        @user_bp.arguments(InviteSchema)
        @user_bp.response(HTTPStatus.OK, InviteSchema)
        def post(self, payload, user_id):
            """Create an invite."""
            current = User.get_current_user()
            if not current or (current.id != user_id and not current.is_admin):
                raise ForbiddenError("Not allowed to send invites")
            payload.sender_user_id = user_id
            invite = Invite(**payload)
            invite.save()
            return invite

        @user_bp.response(HTTPStatus.OK, InviteSchema(many=True))
        def get(self, user_id):
            """List invites sent by user."""
            current = User.get_current_user()
            if not current or (current.id != user_id and not current.is_admin):
                raise ForbiddenError("Not allowed to view invites")
            return Invite.query.filter_by(sender_user_id=user_id).all()

    # Password recovery endpoints
    @user_bp.public_endpoint
    @user_bp.route("/send_recovery_token", methods=["POST"])
    @user_bp.arguments(RecoveryArgsSchema)
    @user_bp.response(HTTPStatus.OK, description="Password reset email sent")
    def send_recovery_token(payload):
        """Send password recovery token."""
        with User.bypass_perms():
            user = User.get_by(email=payload["email"])
        if not user or payload["first_name"].lower() != (user.first_name or "").lower():
            raise UnauthorizedError("Wrong email or first name")

        # Create recovery token (expires in 2 hours)
        token = create_access_token(
            identity=user.id, expires_delta=datetime.timedelta(seconds=3600 * 2)
        )

        # In production, send email with recovery URL
        # send_email(recipients=[user.email], template="recovery", data={"token": token})

        # In development/debug mode, return token
        if app.config["DEBUG"]:
            return {"debug_recovery_token": token}

        return "Password reset email sent", HTTPStatus.OK

    @user_bp.public_endpoint
    @user_bp.route("reset_password", methods=["POST"])
    @user_bp.arguments(PasswordResetSchema)
    @user_bp.response(HTTPStatus.OK, TokenSchema)
    def reset_password(payload):
        """Reset password using recovery token."""
        try:
            token_contents = decode_token(payload["recovery_token"])
            recover_id = token_contents["sub"]
        except Exception:
            raise UnauthorizedError("Invalid token")

        with User.bypass_perms():
            user = User.get_or_404(recover_id)
            user.set_password(payload["new_password"])
            user.save()

        access_token = create_access_token(identity=user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    # Register all blueprints
    api.register_blueprint(user_bp)

    # -------------------------------------------------------------------------
    # Run Application
    # -------------------------------------------------------------------------

    if __name__ == "__main__":
        with app.app_context():
            db.create_all()
        app.run(debug=True)


Key Features Explained
-----------------------

Custom Domain Model
~~~~~~~~~~~~~~~~~~

The ``Domain`` model extends ``AbstractDomain`` to add:

- Multi-tenant support with domain_type field
- Geolocation (lat, lon, area_geojson)
- Custom permission methods (anyone can read, authenticated users can write)

This enables applications like:

- **SaaS platforms** - Multiple organizations/tenants
- **Geo-fenced resources** - Location-based access control
- **Hierarchical domains** - Parent/child domain relationships

Custom User Model
~~~~~~~~~~~~~~~~~~

The ``User`` model combines three sources:

1. **AbstractUser** - Core FMS functionality (email, password, roles, settings, tokens)
2. **ProfileMixin** - first_name, last_name, display_name, avatar_url
3. **SoftDeleteMixin** - deleted_at, is_deleted, soft_delete(), restore()

Custom fields include:

- ``profile_pic_id`` - Link to profile picture image
- ``display_name`` - Custom property showing name with initials
- ``has_domain_access()`` - Multi-tenant permission check

Custom Permission Methods:

- ``_can_read()`` - Users read own profile, admins read all
- ``_can_write()`` - Users edit own profile
- ``_can_create()`` - Only admins create users

Soft Delete Usage:

.. code-block:: python

    # Soft delete a user
    user = User.get_or_404(user_id)
    user.soft_delete()
    user.save()

    # Check if deleted
    if user.is_deleted:
        print(f"User deleted at {user.deleted_at}")

    # Restore user
    user.restore()
    user.save()

    # Soft-deleted users cannot login
    # (is_enabled is automatically set to False)

Login Validation Hooks
~~~~~~~~~~~~~~~~~~~~~

``DemoUserBlueprint`` overrides ``_validate_login()`` to add domain access checks:

.. code-block:: python

    class DemoUserBlueprint(UserBlueprint):
        def _validate_login(self, user: User, data: dict) -> None:
            """Called by FMS after password verification."""
            if domain_name := data.get("domain"):
                domain = Domain.get_by_or_404(name=domain_name)
                if not user.has_domain_access(domain.id):
                    raise UnauthorizedError("No domain access")

This hook is called **after**:

- Password verification (via ``is_password_correct()``)
- Account enabled check (via ``is_enabled`` property)

But **before**:

- JWT token creation
- Return of login response

You can add any validation here:

- Domain access checks (as shown)
- MFA verification
- Rate limiting
- IP-based restrictions
- Custom audit logging

Invite System
~~~~~~~~~~~~

The ``Invite`` model demonstrates custom models that extend ``BasePermsModel``:

- Uses FMS permission system (``_can_read``, ``_can_write``)
- Tracks invite sender, recipient, and status
- Integrates with custom User model

Password Recovery Flow
~~~~~~~~~~~~~~~~~~~~~

Two endpoints handle password reset:

1. **POST /send_recovery_token** - Creates time-limited JWT token
2. **POST /reset_password** - Uses token to set new password

Key security features:

- Token expires after 2 hours
- Email/first name verification required
- Token single-use (not enforced in example, can be tracked)

Health Endpoint
~~~~~~~~~~~~~~~~

FMS automatically registers ``/health`` endpoint when using ``Api``:

.. code-block:: bash

    curl http://localhost:5000/health

Response:

.. code-block:: json

    {
        "status": "healthy",
        "timestamp": "2026-01-26T18:00:00+00:00",
        "version": "0.9.2",
        "database": "connected"
    }

Configure with:

.. code-block:: python

    app.config["HEALTH_ENDPOINT_ENABLED"] = True
    app.config["HEALTH_ENDPOINT_PATH"] = "/health"


Testing This Pattern
-------------------

See :doc:`testing` for testing helpers. Example tests for this pattern
are available in ``tests/integration/test_user_demoapp_integration.py``:

.. code-block:: python

    import pytest
    from flask_more_smorest.testing import as_user, as_admin

    def test_soft_delete(db_session):
        with User.bypass_perms():
            user = User(email="test@example.com")
            user.set_password("password123")
            user.save()

        user.soft_delete()
        assert user.is_deleted
        assert user.deleted_at is not None

    def test_domain_access(db_session):
        with User.bypass_perms():
            domain = Domain(name="test-domain", active=True)
            domain.save()

            user = User(email="user@example.com")
            user.set_password("password123")
            user.save()

            role = UserRole(user_id=user.id, domain_id=domain.id, role="ADMIN")
            role.save()

        # Test login with domain
        client = app.test_client()
        resp = client.post(
            "/api/user/login/",
            json={"email": "user@example.com", "password": "password123", "domain": "test-domain"},
        )
        assert resp.status_code == 200

    def test_admin_only_endpoint(client, db_session):
        with User.bypass_perms():
            user = User(email="user@example.com")
            user.set_password("password123")
            user.save()

            admin = User(email="admin@example.com")
            admin.set_password("admin123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.ADMIN))

        # Regular user: 403 on admin endpoint
        with as_user(client, str(user.id)):
            resp = client.get("/api/user/")
            assert resp.status_code == 403

        # Admin: 200 on admin endpoint
        with as_admin(client, str(admin.id)):
            resp = client.get("/api/user/")
            assert resp.status_code == 200


Migration Guide
----------------

If you're migrating from an existing user system to FMS:

**Step 1: Extend AbstractUser**

.. code-block:: python

    from flask_more_smorest.perms.models.abstract_user import AbstractUser

    class MyUser(AbstractUser):
        # Keep your existing table name
        __tablename__ = "my_users"

        # Your existing fields
        existing_field: Mapped[str] = mapped_column(db.String(100))

        # FMS will add: email, password, is_enabled, roles, settings, tokens

**Step 2: Register with init_fms**

.. code-block:: python

    from flask_more_smorest.perms import init_fms

    init_fms(user=MyUser)

.. note:: **Auto-Loading of Defaults**

   When you call ``init_fms(user=MyUser)``, the system automatically
   imports and registers the default models for UserRole, Token, Domain, and
   UserSetting. No explicit import of default models is needed unless you
   need to reference them in your code.

**Step 3: Use FMS UserBlueprint**

.. code-block:: python

    from flask_more_smorest.perms import UserBlueprint

    user_bp = UserBlueprint(model=MyUser)
    api.register_blueprint(user_bp)

**Step 4: Update imports**

.. code-block:: python

    # Before
    from my_app.auth import get_current_user, is_user_admin

    # After
    from flask_more_smorest.perms import get_current_user, is_current_user_admin


Troubleshooting
---------------

**"No module named 'register_user_class'" error:**

The ``register_user_class`` function was removed in FMS 0.9.0.
Use ``init_fms(user=MyUser)`` instead:

.. code-block:: python

    # Old (doesn't work):
    from flask_more_smorest.perms.user_context import register_user_class
    register_user_class(MyUser)

    # New (correct):
    from flask_more_smorest.perms import init_fms
    init_fms(user=MyUser)

**Soft-deleted users can still login:**

FMS's ``soft_delete()`` automatically sets ``is_enabled=False``.
Ensure you check ``is_enabled`` in login logic (handled by FMS UserBlueprint).

**Custom login validation not working:**

Make sure to override ``_validate_login()`` in a ``UserBlueprint`` subclass:

.. code-block:: python

    class MyUserBlueprint(UserBlueprint):
        def _validate_login(self, user: User, data: dict) -> None:
            # Your custom validation here
            if domain_name := data.get("domain"):
                if not user.has_domain_access(domain_name):
                    raise UnauthorizedError("No domain access")

**Health endpoint not working:**

Ensure you're using FMS's ``Api`` class (not Flask-Smorest's):

.. code-block:: python

    # Correct
    from flask_more_smorest.perms import Api
    api = Api(app)

    # Wrong (health endpoint won't be registered)
    from flask_smorest import Api
    api = Api(app)


.. seealso::

   :doc:`user-extension`
      Comprehensive guide for extending User models.

   :doc:`custom-user-context`
      Integrating with external authentication systems.

   :doc:`testing`
      Testing helpers for authenticated endpoints.
