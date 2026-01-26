User Model Extension Guide
============================

Flask-More-Smorest provides flexible options for extending the User model to meet your application's needs. This guide helps you choose the right approach and implement it correctly.

.. tip:: **Quick Decision**

   - **Just adding fields?** → Direct inheritance (Pattern 1)
   - **Distinct user types?** → Separate tables (Pattern 2)
   - **Existing auth system?** → Custom user context (Pattern 3)
   - **External auth (OAuth, SAML)?** → Custom user context (Pattern 3)

.. contents:: Table of Contents
   :local:
   :depth: 2

----------------------------------------------------
Pattern 1: Direct Inheritance (90% of Use Cases)
----------------------------------------------------

Use direct inheritance when you want to add fields to the built-in User model while keeping all authentication and permission functionality.

**When to Use:**
- Adding profile fields (bio, phone, etc.)
- Adding custom properties or methods
- Most common use cases

**Single Table Inheritance (default):**

.. code-block:: python

   from flask_more_smorest.perms.models.defaults import User
   from sqlalchemy.orm import Mapped, mapped_column

   class CustomUser(User):
       # Uses "user" table (single-table inheritance)
       bio: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
       phone: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
       age: Mapped[int | None] = mapped_column(db.Integer, nullable=True)

       @property
       def is_adult(self) -> bool:
           return self.age is not None and self.age >= 18

All User instances automatically include:
- Email authentication with password hashing
- Role management via ``User.roles`` relationship
- User settings via ``User.settings`` relationship
- JWT tokens via ``User.tokens`` relationship
- Permission methods (``is_admin``, ``is_superadmin``, ``has_role``)

**Overriding Permission Methods:**

.. code-block:: python

   class VerifiedUser(User):
       is_verified: Mapped[bool] = mapped_column(db.Boolean, default=False)

       def _can_write(self) -> bool:
           """Only verified users can edit their own profile."""
           if self.is_current_user_admin():
               return True
           if self.id == get_current_user_id():
               return self.is_verified
           return super()._can_write()

**Using Mixins for Common Features:**

.. code-block:: python

   from flask_more_smorest.perms import ProfileMixin, TimestampMixin, SoftDeleteMixin

   class FullUser(User, ProfileMixin, TimestampMixin, SoftDeleteMixin):
       # Adds: first_name, last_name, display_name, avatar_url
       # Adds: last_login_at, email_verified_at
       # Adds: deleted_at, is_deleted, soft_delete(), restore()
       pass

.. _pattern-separate-tables:

----------------------------------------------------
Pattern 2: Separate Tables (Distinct User Types)
----------------------------------------------------

Use separate tables when you have distinct types of users that need their own schema.

**When to Use:**
- Different user types (employees, contractors, customers)
- Avoiding table conflicts
- Cleaner schema separation

**Joined Table Inheritance:**

.. code-block:: python

   class ContractorUser(User):
       __tablename__ = "contractor_users"
       id: Mapped[uuid.UUID] = mapped_column(
           sa.Uuid(as_uuid=True),
           db.ForeignKey("user.id"),
           primary_key=True
       )
       contractor_id: Mapped[str] = mapped_column(db.String(50), unique=True)
       hourly_rate: Mapped[float] = mapped_column(db.Float)

       # Inherits all User functionality via FK relationship

**No Inheritance (Completely Separate):**

.. code-block:: python

   class CustomerProfile(BaseModel):
       """Separate profile table linked to User."""
       __tablename__ = "customer_profiles"
       user_id: Mapped[uuid.UUID] = mapped_column(
           sa.Uuid(as_uuid=True),
           db.ForeignKey("user.id"),
           nullable=False
       )
       user: Mapped[User] = relationship("User")
       preferences: Mapped[dict] = mapped_column(db.JSON, default={})

----------------------------------------------------
Pattern 3: Custom User Context (External Auth)
----------------------------------------------------

Use custom user context when you have an existing authentication system or use external providers.

**When to Use:**
- Existing User/UserRole models in your app
- OAuth, SAML, LDAP integration
- Multi-tenant with distinct user models per tenant
- Want complete control over User model

**Registering Custom User Context:**

Register your custom user class (and optionally a custom getter):

.. code-block:: python

   from flask_login import current_user
   from flask_more_smorest.perms import init_fms

   def get_flask_login_user():
       return current_user if not current_user.is_anonymous else None

   # Register - everything else derives from this!
   init_fms(user=MyUser, get_current_user=get_flask_login_user)

The system automatically provides:

- ``get_current_user()`` - Calls your registered function
- ``get_current_user_id()`` - Extracts ``id`` attribute from your user
- ``is_current_user_admin()`` - Checks ``has_role('admin')``
- ``is_current_user_superadmin()`` - Checks ``has_role('superadmin')``
- ``list_roles()`` - Returns user's roles as strings (if implemented)

**UserProtocol for Type Safety:**

Your custom User model should implement ``UserProtocol`` for compatibility:

.. code-block:: python

   from flask_more_smorest.perms import UserProtocol, ROLE_ADMIN, ROLE_SUPERADMIN
   from typing import runtime_checkable
   import uuid

   @runtime_checkable
   class MyUser(UserProtocol):
       id: uuid.UUID
       email: str
       roles: list[str] = []

       def has_role(self, role: str) -> bool:
           return role in self.roles

       def list_roles(self) -> list[str]:
           return list(self.roles)

   # Type checking works
   user: MyUser = get_current_user()
   if isinstance(user, UserProtocol):
       print(f"User {user.email} is compliant")

**Integration Examples:**

*Flask-Login:*

.. code-block:: python

   from flask_login import current_user
   from flask_more_smorest.perms import init_fms

   def get_flask_login_user():
       return current_user if not current_user.is_anonymous else None

   init_fms(user=MyUser, get_current_user=get_flask_login_user)

*Custom OAuth (Google, GitHub, etc.):*

.. code-block:: python

   from authlib.integrations.flask_client import OAuth
   from flask_more_smorest.perms import init_fms

   oauth = OAuth()

   def get_oauth_user():
       from flask import session
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None

   init_fms(user=MyUser, get_current_user=get_oauth_user)

   # Your User model needs has_role method:
   class MyUser:
       def has_role(self, role: str) -> bool:
           return role in ['admin', 'superadmin']

       def list_roles(self) -> list[str]:
           return ['admin'] if self.is_admin else []

*Multi-Tenant with Distinct User Models:*

.. code-block:: python

   from flask import g
   from flask_more_smorest.perms import init_fms

   def get_tenant_user():
       if not hasattr(g, 'tenant_id'):
           return None
       return get_tenant_user_model(g.tenant_id).get_current_user()

   init_fms(user=get_tenant_user_model(g.tenant_id), get_current_user=get_tenant_user)

   # Your User model needs has_role method:
   class MyUser:
       def has_role(self, role: str) -> bool:
           if role == 'admin':
               return self.is_tenant_admin()
           if role == 'superadmin':
               return self.is_platform_admin()
           return False

       def list_roles(self) -> list[str]:
           roles = []
           if self.is_tenant_admin():
               roles.append('admin')
           if self.is_platform_admin():
               roles.append('superadmin')
           return roles

----------------------------------
Available Mixins
----------------------------------

Flask-More-Smorest provides several mixins for common functionality.

**ProfileMixin** - User profile information:

.. code-block:: python

   from flask_more_smorest.perms import ProfileMixin

   class ProfileUser(User, ProfileMixin):
       # Adds: first_name, last_name, display_name, avatar_url
       # Plus: full_name property
       pass

**TimestampMixin** - Additional timestamps:

.. code-block:: python

   from flask_more_smorest.perms import TimestampMixin

   class TimestampUser(User, TimestampMixin):
       # Adds: last_login_at, email_verified_at
       pass

**SoftDeleteMixin** - Soft delete support:

.. code-block:: python

   from flask_more_smorest.perms import SoftDeleteMixin

   class SoftDeleteUser(User, SoftDeleteMixin):
       # Adds: deleted_at, is_deleted, soft_delete(), restore()
       pass

**UserOwnershipMixin** - User-owned resources:

.. code-block:: python

   from flask_more_smorest.perms import UserOwnershipMixin

   class Note(UserOwnershipMixin, BasePermsModel):
       # Adds: user_id, user relationship
       # Automatic permission checks (owner can read/write)
       content: Mapped[str] = mapped_column(db.Text)

**HasUserMixin** - Simple user reference:

.. code-block:: python

   from flask_more_smorest.perms import HasUserMixin

   class Comment(HasUserMixin, BasePermsModel):
       # Adds: user_id, user relationship
       # Configurable via __user_field_name__, etc.
       text: Mapped[str] = mapped_column(db.Text)

-------------------------------
Common Use Cases
-------------------------------

Multi-Tenant SaaS Application
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class TenantUser(User):
       tenant_id: Mapped[uuid.UUID] = mapped_column(db.ForeignKey('tenant.id'))
       feature_flags: Mapped[dict] = mapped_column(db.JSON, default={})

       def has_feature(self, feature: str) -> bool:
           return self.feature_flags.get(feature, False)

       def _can_read(self) -> bool:
           """Users can only read within their tenant."""
           current = get_current_user()
           return bool(current and (
               current.tenant_id == self.tenant_id or current.is_admin
           ))

E-Commerce Platform
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class CustomerUser(User, ProfileMixin, TimestampMixin):
       customer_type: Mapped[str] = mapped_column(db.String(20), default="retail")
       loyalty_points: Mapped[int] = mapped_column(db.Integer, default=0)
       preferred_currency: Mapped[str] = mapped_column(db.String(3), default="USD")

       @property
       def loyalty_tier(self) -> str:
           if self.loyalty_points >= 10000:
               return "platinum"
           elif self.loyalty_points >= 5000:
               return "gold"
           return "bronze"

Enterprise Application
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class EmployeeUser(User, ProfileMixin, TimestampMixin):
       employee_id: Mapped[str] = mapped_column(db.String(20), unique=True)
       hire_date: Mapped[date] = mapped_column(db.Date)
       position: Mapped[str] = mapped_column(db.String(100))
       manager_id: Mapped[uuid.UUID | None] = mapped_column(db.ForeignKey('user.id'))

       manager: Mapped["EmployeeUser | None"] = relationship(
           "EmployeeUser", remote_side="EmployeeUser.id"
       )

       @property
       def years_of_service(self) -> int:
           return (date.today() - self.hire_date).days // 365

       def _can_read(self) -> bool:
           """Employees can read own data and direct reports."""
           current = get_current_user()
           if not current:
               return False
           if current.id == self.id or current.is_admin:
               return True
           return self.manager_id == current.id

Troubleshooting
---------------

**"Table 'user' is already defined" Error:**

- *Cause:* Multiple classes using single-table inheritance without proper config
- *Solution:* Use ``__tablename__`` for separate tables or ensure ``__table_args__ = {"extend_existing": True}`` is set

**Custom role enums not working with permissions:**

- *Cause:* Hardcoded role checking in ``UserRole._can_write()``
- *Solution:* Now uses string matching for custom role names; ensure custom roles include "admin" or "superadmin" when appropriate.

**"Working outside of request context" Error:**

- *Cause:* Calling ``get_current_user()`` outside Flask request context
- *Solution:* Use ``with app.test_request_context():`` for testing, or catch ``RuntimeError`` gracefully

.. seealso::

   :doc:`permissions`
      Learn about the permission system and how it works with user context.

   :doc:`custom-user-context`
      Detailed examples of external auth integration.
