Custom User Context
===================

Flask-More-Smorest provides a pluggable user context system that allows you to integrate your own User models and authentication systems while still leveraging the permission system.

.. contents:: Table of Contents
   :local:
   :depth: 2

Why Custom User Context?
-------------------------

You might want to use custom user context when:

- Your application already has a User model with its own table structure
- You're integrating flask-more-smorest into an existing application
- You have custom authentication logic (OAuth, SAML, etc.)
- You want to avoid SQLAlchemy table name conflicts
- You need integration with third-party user management systems

Without configuration, flask-more-smorest uses its built-in ``User`` and ``UserRole`` models. This can cause table name conflicts if your application defines models with the same table names.

Quick Start
-----------

Minimal configuration using registration functions:

.. code-block:: python

   from flask_more_smorest.perms import (
       register_get_current_user,
       register_get_current_user_id,
   )
   
   def get_my_user():
       # Your custom logic to get current user
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None
   
   def get_my_user_id():
       # Your custom logic to get current user ID
       return session.get('user_id')
   
   # Register your functions
   register_get_current_user(get_my_user)
   register_get_current_user_id(get_my_user_id)

Now all permission checks use your custom user context.

Configuration Options
---------------------

There are three ways to configure user context, listed in order of precedence:

1. Flask Config (Highest Priority)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure via Flask application config:

.. code-block:: python

   from flask import Flask
   
   app = Flask(__name__)
   app.config['FMS_GET_CURRENT_USER'] = get_my_user
   app.config['FMS_GET_CURRENT_USER_ID'] = get_my_user_id
   app.config['FMS_IS_CURRENT_USER_ADMIN'] = lambda: get_my_user().is_admin

**Pros:**

- Per-application configuration
- Easy to override in different environments
- Follows Flask conventions

**Cons:**

- Requires app context

2. Global Registration
^^^^^^^^^^^^^^^^^^^^^^^

Register functions globally using registration API:

.. code-block:: python

   from flask_more_smorest.perms import (
       register_get_current_user,
       register_get_current_user_id,
       register_is_current_user_admin,
   )
   
   register_get_current_user(get_my_user)
   register_get_current_user_id(get_my_user_id)
   register_is_current_user_admin(lambda: get_my_user().is_admin)

**Pros:**

- Works outside app context
- Simple, straightforward API
- Good for single-app projects

**Cons:**

- Global state
- Cannot differ per application

3. Built-in Fallback (Default)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If neither config nor registration is set, flask-more-smorest uses its built-in user models:

.. code-block:: python

   # Automatic fallback to built-in
   from flask_more_smorest.perms.user_models import (
       get_current_user,
       get_current_user_id,
   )

**Pros:**

- Zero configuration
- Works out of the box
- Good for new projects

**Cons:**

- May conflict with existing User models
- Less flexible

User Protocol
-------------

Your custom User model should conform to ``UserProtocol`` for type safety:

.. code-block:: python

   import uuid
   from flask_more_smorest.perms import UserProtocol
   
   class MyUser:
       """Custom User model implementing UserProtocol."""
       
       def __init__(self, id: uuid.UUID, email: str, is_admin: bool):
           self.id = id
           self.email = email
           self._is_admin = is_admin
       
       @property
       def is_admin(self) -> bool:
           """Required by UserProtocol."""
           return self._is_admin

**Required Attributes:**

- ``id: uuid.UUID`` - Unique user identifier
- ``is_admin: bool`` - Property indicating admin status

.. note::

   ``UserProtocol`` is a :py:class:`typing.Protocol`, so you don't need to explicitly inherit from it. Any class with matching attributes will be considered conforming.

Complete Examples
-----------------

Example 1: Flask-Login Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Integrate with Flask-Login:

.. code-block:: python

   from flask import Flask
   from flask_login import LoginManager, current_user
   from flask_more_smorest.perms import (
       register_get_current_user,
       register_get_current_user_id,
   )
   
   app = Flask(__name__)
   login_manager = LoginManager(app)
   
   # Your existing User model
   class User(db.Model):
       id = db.Column(db.String(36), primary_key=True)
       email = db.Column(db.String(255), unique=True)
       is_admin = db.Column(db.Boolean, default=False)
   
   @login_manager.user_loader
   def load_user(user_id):
       return User.query.get(user_id)
   
   # Configure flask-more-smorest to use Flask-Login
   register_get_current_user(lambda: current_user if current_user.is_authenticated else None)
   register_get_current_user_id(lambda: current_user.id if current_user.is_authenticated else None)

Example 2: JWT with Custom Claims
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use custom JWT claims for user context:

.. code-block:: python

   from flask import Flask
   from flask_jwt_extended import JWTManager, get_jwt_identity, get_jwt
   from flask_more_smorest.perms import (
       register_get_current_user,
       register_get_current_user_id,
       register_is_current_user_admin,
   )
   
   app = Flask(__name__)
   jwt = JWTManager(app)
   
   # Custom User model
   class User:
       def __init__(self, id, email, is_admin):
           self.id = id
           self.email = email
           self.is_admin = is_admin
   
       @staticmethod
       def get(user_id):
           # Load from database or cache
           return User.query.get(user_id)
   
   # Add custom claims to JWT
   @jwt.additional_claims_loader
   def add_claims_to_jwt(identity):
       user = User.get(identity)
       return {
           'is_admin': user.is_admin,
           'email': user.email,
       }
   
   # Configure user context
   def get_current_user():
       user_id = get_jwt_identity()
       return User.get(user_id) if user_id else None
   
   def get_current_user_id():
       return get_jwt_identity()
   
   def is_current_user_admin():
       claims = get_jwt()
       return claims.get('is_admin', False)
   
   register_get_current_user(get_current_user)
   register_get_current_user_id(get_current_user_id)
   register_is_current_user_admin(is_current_user_admin)

Example 3: OAuth / Third-Party Auth
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Integrate with external authentication providers:

.. code-block:: python

   from flask import Flask, session
   from flask_more_smorest.perms import register_get_current_user, register_get_current_user_id
   
   app = Flask(__name__)
   
   # User data comes from OAuth provider
   class OAuthUser:
       def __init__(self, oauth_data):
           self.id = oauth_data['sub']  # OAuth subject claim
           self.email = oauth_data['email']
           self.is_admin = oauth_data.get('roles', []).contains('admin')
   
   def get_current_user():
       oauth_data = session.get('oauth_user')
       return OAuthUser(oauth_data) if oauth_data else None
   
   def get_current_user_id():
       oauth_data = session.get('oauth_user')
       return oauth_data.get('sub') if oauth_data else None
   
   register_get_current_user(get_current_user)
   register_get_current_user_id(get_current_user_id)

Example 4: Multi-Tenant with Different User Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Different user models per tenant:

.. code-block:: python

   from flask import Flask, g
   from flask_more_smorest.perms import UserProtocol
   
   app = Flask(__name__)
   
   # Different user models per tenant
   class TenantAUser:
       id: uuid.UUID
       @property
       def is_admin(self) -> bool:
           return self.role == 'admin'
   
   class TenantBUser:
       id: uuid.UUID
       @property
       def is_admin(self) -> bool:
           return 'admin' in self.permissions
   
   # Use Flask config for per-request resolution
   def get_current_user():
       tenant = g.get('tenant')
       if tenant == 'tenant_a':
           return TenantAUser.get_current()
       elif tenant == 'tenant_b':
           return TenantBUser.get_current()
       return None
   
   app.config['FMS_GET_CURRENT_USER'] = get_current_user

Testing Custom User Context
----------------------------

When testing, you can provide mock user context:

.. code-block:: python

   import pytest
   from flask_more_smorest.perms import (
       register_get_current_user,
       clear_registrations,
   )
   
   class MockUser:
       def __init__(self, id, is_admin=False):
           self.id = id
           self.is_admin = is_admin
   
   @pytest.fixture
   def mock_admin_user():
       """Provide a mock admin user for testing."""
       user = MockUser(id=uuid.uuid4(), is_admin=True)
       register_get_current_user(lambda: user)
       yield user
       clear_registrations()  # Clean up after test
   
   def test_admin_access(mock_admin_user):
       # Test uses mock admin user
       result = some_protected_function()
       assert result.success

Best Practices
--------------

1. **Type Safety**
   
   Ensure your User model conforms to ``UserProtocol``:

   .. code-block:: python

      from flask_more_smorest.perms import UserProtocol
      
      # Type checker will verify conformance
      def get_my_user() -> UserProtocol | None:
          return MyUser.get_current()

2. **Error Handling**
   
   Handle missing or invalid user gracefully:

   .. code-block:: python

      def get_current_user():
          try:
              user_id = get_jwt_identity()
              return User.query.get(user_id)
          except Exception as e:
              logger.error(f"Error getting current user: {e}")
              return None

3. **Performance**
   
   Cache user lookups to avoid repeated database queries:

   .. code-block:: python

      from flask import g
      
      def get_current_user():
          if not hasattr(g, 'current_user'):
              user_id = get_jwt_identity()
              g.current_user = User.query.get(user_id) if user_id else None
          return g.current_user

4. **Security**
   
   Validate user state before returning:

   .. code-block:: python

      def get_current_user():
          user = _load_user_from_session()
          if user and not user.is_active:
              # Don't return disabled users
              return None
          return user

Troubleshooting
---------------

Issue: Permission checks not using custom user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Problem:** Permissions still use built-in User model.

**Solution:** Ensure registration happens before importing permission models:

.. code-block:: python

   # Do this FIRST
   from flask_more_smorest.perms import register_get_current_user
   register_get_current_user(my_func)
   
   # Then import models that use permissions
   from my_app.models import Article

Issue: Table name conflicts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Problem:** SQLAlchemy raises "Table 'users' is already defined" error.

**Solution:** Configure custom user context to avoid flask-more-smorest's built-in User model:

.. code-block:: python

   register_get_current_user(my_get_user)
   register_get_current_user_id(my_get_user_id)
   # Don't import or use flask_more_smorest.perms.user_models.User

Issue: Tests fail with "Working outside request context"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Problem:** Tests fail because user context requires request/app context.

**Solution:** Use test fixtures with proper context or mock user functions:

.. code-block:: python

   @pytest.fixture
   def app_context(app):
       with app.app_context():
           yield

API Reference
-------------

.. py:function:: register_get_current_user(func: Callable[[], Any]) -> None

   Register a function to get the current user.
   
   :param func: Function that returns current user or None
   :type func: Callable[[], Any]

.. py:function:: register_get_current_user_id(func: Callable[[], uuid.UUID | None]) -> None

   Register a function to get the current user's ID.
   
   :param func: Function that returns current user's UUID or None
   :type func: Callable[[], uuid.UUID | None]

.. py:function:: register_is_current_user_admin(func: Callable[[], bool]) -> None

   Register a function to check if current user is admin.
   
   :param func: Function that returns True if current user is admin
   :type func: Callable[[], bool]

.. py:function:: clear_registrations() -> None

   Clear all registered user context functions. Useful for testing.

.. py:class:: UserProtocol

   Protocol defining minimum interface for User objects.
   
   .. py:attribute:: id
      :type: uuid.UUID
      
      Unique user identifier.
   
   .. py:attribute:: is_admin
      :type: bool
      
      Whether user has admin privileges (must be a property).

Next Steps
----------

- See :doc:`permissions` for using custom users with permission models
- Check :doc:`user-models` for built-in user model documentation
- Review :doc:`configuration` for Flask config options
