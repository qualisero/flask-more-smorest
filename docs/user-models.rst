User Models & Authentication
============================

Flask-More-Smorest includes a built-in user system with authentication, roles, and token management.

Overview
--------

The user system provides:

- Pre-built ``User`` model with email/password authentication
- Role-based access control with ``UserRole`` and ``DefaultUserRole``
- JWT token management with ``Token`` objects (refresh/API tokens)
- Profile and timestamp mixins for extended user data
- Easy extension for custom user models

Basic Usage
-----------

Import and use the default user models:

.. code-block:: python

   from flask_more_smorest.perms import User, UserRole, DefaultUserRole

   # Create a user
   user = User(email="admin@example.com")
   user.set_password("secret123")
   user.save()

   # Assign admin role
   UserRole(user=user, role=DefaultUserRole.ADMIN).save()

   # Verify password
   if user.is_password_correct("secret123"):
       print("Password correct!")

   # Check if user has a role
   if user.has_role(DefaultUserRole.ADMIN):
       print("User is an admin!")

User Model
----------

The ``User`` model provides:

Fields
^^^^^^

- ``email``: str - Unique email address (required)
- ``password``: bytes | None - Hashed password storage (set via ``set_password``)
- ``is_enabled``: bool - Whether user account is enabled (default: True)
- ``id``: UUID - Inherited from BasePermsModel
- ``created_at``, ``updated_at``: datetime - Inherited from BasePermsModel

Methods
^^^^^^^

Password Management:

.. code-block:: python

   user = User(email="user@example.com")
   
   # Set password (automatically hashed with bcrypt)
   user.set_password("my-secure-password")
   
   # Check password
   if user.is_password_correct("my-secure-password"):
       print("Correct!")

Role Management:

.. code-block:: python

   # Check if user has a specific role
   if user.has_role(DefaultUserRole.ADMIN):
       print("Admin user")
   
   # Check if user has any role
   if user.has_role():
       print("User has at least one role")
   
   # Get all user roles
   roles = user.roles  # List of UserRole objects

Token Management:

.. code-block:: python

   # Get user's tokens
   tokens = user.tokens  # List of Token objects

Default Roles
-------------

``DefaultUserRole`` enum provides common roles:

.. code-block:: python

   from flask_more_smorest.perms import DefaultUserRole

   # Available roles
   DefaultUserRole.SUPERADMIN  # Super administrator
   DefaultUserRole.ADMIN       # Administrator
   DefaultUserRole.USER        # Regular user

Assigning Roles:

.. code-block:: python

   from flask_more_smorest.perms import User, UserRole, DefaultUserRole

   user = User.query.filter_by(email="user@example.com").first()
   
   # Add admin role
   UserRole(user=user, role=DefaultUserRole.ADMIN).save()
   
   # Add another role
   UserRole(user=user, role=DefaultUserRole.SUPERADMIN).save()

Removing Roles:

.. code-block:: python

   # Find and delete specific role
   role = UserRole.query.filter_by(
       user_id=user.id,
       role=DefaultUserRole.MODERATOR
   ).first()
   if role:
       role.delete()

User Authentication Blueprints
------------------------------

The easiest way to add authentication is with ``UserBlueprint``:

``UserBlueprint`` features:

- Auto-generated CRUD endpoints for the configured user model (list, detail, create, update, delete)
- Built-in authentication endpoints: ``POST /login/`` and ``GET /me/``
- Respects all ``CRUDBlueprint`` options (``url_prefix``, ``methods``, ``skip_methods``, etc.)
- Uses the provided ``model`` and ``schema`` classes (defaults to ``User`` and ``User.Schema``)
- Automatically marks ``POST`` as public when ``model.PUBLIC_REGISTRATION`` is ``True``
- Supports multiple instances (e.g., admin vs public endpoints)


.. code-block:: python

   from flask_more_smorest import UserBlueprint
   from flask_more_smorest.perms import init_fms
   from flask_more_smorest.perms.models.defaults import (
       DefaultDomain,
       DefaultToken,
       DefaultUser,
       DefaultUserRole,
       DefaultUserSetting,
   )

   # Register default models explicitly
   init_fms(
       user=DefaultUser,
       role=DefaultUserRole,
       token=DefaultToken,
       domain=DefaultDomain,
       setting=DefaultUserSetting,
   )

   # Instant authentication endpoints
   user_bp = UserBlueprint(register=False)
   api.register_blueprint(user_bp)

This automatically provides:

- ``POST /api/users/login/`` - JWT authentication
- ``GET /api/users/me/`` - Current user profile
- Full CRUD endpoints for user management

Enable Public Registration:

.. code-block:: python

   from flask_more_smorest import UserBlueprint
   from flask_more_smorest.perms.models.defaults import DefaultUser

   class PublicUser(DefaultUser):
       PUBLIC_REGISTRATION = True  # Allow unauthenticated user creation

   public_bp = UserBlueprint(model=PublicUser, register=False)
   api.register_blueprint(public_bp)

Customize UserBlueprint:

You can either configure ``methods``/``skip_methods`` dictionaries or subclass ``UserBlueprint``.

.. code-block:: python

   from flask_more_smorest.crud.crud_blueprint import CRUDMethod

   # Custom configuration
   custom_bp = UserBlueprint(
       model=Employee,
       schema=Employee.Schema,
       name="auth",
       url_prefix="/api/auth/",
       skip_methods=[CRUDMethod.DELETE],  # Disable user deletion
   )

   # Override schema/args for CRUD create endpoint (e.g., invite-only signup)
   from myapp.schemas import InviteSignupSchema

   invite_bp = UserBlueprint(
       methods={
           CRUDMethod.POST: {
               "arg_schema": InviteSignupSchema,
               "schema": PublicUser.Schema,
           }
       }
   )

   # Subclass for custom login response or validation
   class AdminUserBlueprint(UserBlueprint):
       def _register_login_endpoint(self) -> None:
           super()._register_login_endpoint()
           # Additional admin-specific setup here

   admin_bp = AdminUserBlueprint(model=AdminUser, schema=AdminUser.Schema)

For deeper customization you can override ``_register_login_endpoint`` or ``_register_current_user_endpoint`` in a subclass and call ``super()`` to retain default behavior.

JWT Authentication (Manual Implementation)
------------------------------------------

For custom authentication flows, you can manually implement JWT authentication.

Configuration:

.. code-block:: python

   from flask import Flask
   from flask_more_smorest.perms import Api

   app = Flask(__name__)
   app.config.update(
       SECRET_KEY="your-secret-key",
       JWT_SECRET_KEY="your-jwt-secret",
       JWT_ACCESS_TOKEN_EXPIRES=3600,  # 1 hour
       JWT_REFRESH_TOKEN_EXPIRES=2592000,  # 30 days
   )

   api = Api(app)  # Automatically initializes JWT

Manual Login Endpoint:

.. code-block:: python

   from flask import Blueprint
   from flask_jwt_extended import create_access_token, create_refresh_token
   from flask_more_smorest.perms import User

   auth = Blueprint("auth", __name__)

   @auth.route("/login", methods=["POST"])
   def login():
       data = request.get_json()
       user = User.query.filter_by(email=data["email"]).first()
       
       if not user or not user.is_password_correct(data["password"]):
           return {"error": "Invalid credentials"}, 401
       
       if not user.is_enabled:
           return {"error": "Account disabled"}, 403
       
       access_token = create_access_token(identity=user.id)
       refresh_token = create_refresh_token(identity=user.id)
       
       return {
           "access_token": access_token,
           "refresh_token": refresh_token,
       }

Protected Endpoints:

.. code-block:: python

   from flask_jwt_extended import jwt_required, get_jwt_identity

   @auth.route("/profile")
   @jwt_required()
   def profile():
       user_id = get_jwt_identity()
       user = User.get_by_or_404(id=user_id)
       return UserSchema().dump(user)

Token Management
----------------

Token Model
-----------

The ``Token`` model stores refresh/API tokens and delegates permissions to the owning user. Tokens inherit ``UserOwnershipMixin`` with ``__delegate_to_user__ = True`` so permissions mirror the owning user's permissions.

Fields:

- ``token``: str - Token value (refresh token, API key, etc.)
- ``description``: str | None - Optional description for UI display
- ``expires_at``: datetime | None - Expiration timestamp
- ``revoked`` / ``revoked_at``: Track revocation state

.. code-block:: python

   from flask_more_smorest.perms import Token
   from flask_jwt_extended import create_refresh_token

   # Create and store token
   refresh_token = create_refresh_token(identity=user.id)
   token = Token(
       user_id=user.id,
       token=refresh_token,
       description="CLI token",
       expires_at=datetime.utcnow() + timedelta(days=30)
   )
   token.save()

   # Revoke token
   token.update(revoked=True, revoked_at=datetime.utcnow())

   # Clean up expired tokens
   Token.query.filter(
       Token.expires_at < datetime.utcnow()
   ).delete()

Extending User Model
--------------------

Create custom user models by inheriting from ``User``:

Basic Extension:

.. code-block:: python

   from flask_more_smorest.perms import User
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   class Employee(DefaultUser):
       employee_id: Mapped[str] = mapped_column(
           db.String(32), unique=True, nullable=False
       )
       department: Mapped[str] = mapped_column(db.String(100))
       hire_date: Mapped[datetime] = mapped_column(db.DateTime)

With Profile Mixin:

.. code-block:: python

   from flask_more_smorest.perms import User, ProfileMixin

   class Customer(ProfileMixin, User):
       loyalty_points: Mapped[int] = mapped_column(db.Integer, default=0)
       # ProfileMixin adds: first_name, last_name, phone, address, etc.

With Timestamps Mixin:

.. code-block:: python

   from flask_more_smorest.perms import User, TimestampMixin

   class Member(TimestampMixin, User):
       # Table name automatically set to "member"
       
       membership_level: Mapped[str] = mapped_column(db.String(20))
       # TimestampMixin adds: created_at, updated_at

Multi-Tenant Users:

.. code-block:: python

   from flask_more_smorest.perms import User, HasUserMixin
   import uuid

   class TenantUser(HasUserMixin, User):
       # Table name automatically set to "tenant_user"
       
       # HasUserMixin adds user_id and user relationship
       # Customize to support multi-tenant patterns as needed

Profile Mixin
-------------

``ProfileMixin`` adds common profile fields:

.. code-block:: python

   from flask_more_smorest.perms import ProfileMixin, User

   class UserProfile(ProfileMixin, User):
       # Table name automatically set to "user_profile"
       pass

Fields added by ProfileMixin:

- ``first_name``: str
- ``last_name``: str
- ``phone``: str (optional)
- ``address``: str (optional)
- ``city``: str (optional)
- ``state``: str (optional)
- ``postal_code``: str (optional)
- ``country``: str (optional)

Domain/Multi-Tenancy
--------------------

Multi-tenant patterns are typically implemented using ``Domain`` and ``UserRole`` (roles scoped to domains) or your own mixins.
See :doc:`custom-user-context` for integrating existing multi-tenant models.

Custom Roles
------------

Define custom roles for your application:

.. code-block:: python

   import enum
   from flask_more_smorest.perms import UserRole, User

   class CustomRole(enum.StrEnum):
       SUPER_ADMIN = "super_admin"
       EDITOR = "editor"
       VIEWER = "viewer"
       CONTRIBUTOR = "contributor"

   # Assign custom role
   user = User.get_by(email="editor@example.com")
   UserRole(user=user, role=CustomRole.EDITOR).save()

   # Check custom role
   if user.has_role(CustomRole.EDITOR):
       print("User is an editor")

Permission Integration
----------------------

User models integrate with the permission system:

.. code-block:: python

   from flask_more_smorest.perms import (
       BasePermsModel,
       HasUserMixin,
       UserOwnershipMixin,
   )

   class UserDocument(HasUserMixin, UserOwnershipMixin, BasePermsModel):
       # Table name automatically set to "user_document"
       # Uses default: __delegate_to_user__ = False (simple ownership)
       
       title: Mapped[str] = mapped_column(db.String(200))
       content: Mapped[str] = mapped_column(db.Text)
       
       # Permissions automatically enforced:
       # - Users can only access their own documents
       # - Admins can access all documents

Example: Complete Auth System
------------------------------

Here's a complete authentication system:

.. code-block:: python

   from flask import Flask, Blueprint, request
   from flask_jwt_extended import (
       create_access_token,
       create_refresh_token,
       jwt_required,
       get_jwt_identity,
   )
   from flask_more_smorest import init_db
   from flask_more_smorest.perms import (
       Api,
       User,
       UserRole,
       DefaultUserRole,
       CRUDBlueprint,
   )

   app = Flask(__name__)
   app.config.update(
       SQLALCHEMY_DATABASE_URI="sqlite:///app.db",
       SECRET_KEY="secret",
       JWT_SECRET_KEY="jwt-secret",
   )

   init_db(app)
   api = Api(app)

   # Auth blueprint
   auth = Blueprint("auth", __name__, url_prefix="/auth")

   @auth.route("/register", methods=["POST"])
   def register():
       data = request.get_json()
       
       if User.query.filter_by(email=data["email"]).first():
           return {"error": "Email already exists"}, 400
       
       user = User(email=data["email"])
       user.set_password(data["password"])
       user.save()
       
       # Assign default user role
       UserRole(user=user, role=DefaultUserRole.USER).save()
       
       return {"message": "User created"}, 201

   @auth.route("/login", methods=["POST"])
   def login():
       data = request.get_json()
       user = User.query.filter_by(email=data["email"]).first()
       
       if not user or not user.is_password_correct(data["password"]):
           return {"error": "Invalid credentials"}, 401
       
       access_token = create_access_token(identity=str(user.id))
       refresh_token = create_refresh_token(identity=str(user.id))
       
       return {
           "access_token": access_token,
           "refresh_token": refresh_token,
       }

   @auth.route("/profile")
   @jwt_required()
   def profile():
       user_id = get_jwt_identity()
       user = User.get_by_or_404(id=user_id)
       return {
           "id": str(user.id),
           "email": user.email,
           "is_enabled": user.is_enabled,
           "roles": [role.role for role in user.roles],
       }

   app.register_blueprint(auth)

   # Users management (admin only)
   users_bp = CRUDBlueprint(
       "users",
       __name__,
       model=User,
       schema=User.Schema,
       url_prefix="/api/users/",
       methods={
           CRUDMethod.DELETE: {"admin_only": True},
           CRUDMethod.PATCH: {"admin_only": True},
       },
   )

   api.register_blueprint(users_bp)

Next Steps
----------

- Learn about :doc:`permissions` for access control
- See :doc:`crud` for creating user management endpoints
- Check the :doc:`api` reference for detailed model documentation
