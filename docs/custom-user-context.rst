Custom User Context Integration
================================

Advanced integration examples for using external authentication systems with flask-more-smorest's permission system.

.. tip::
   Looking to extend the User model? See :doc:`user-extension` for extension patterns.
   This guide covers integrating with external auth providers.

.. contents:: Table of Contents
   :local:
   :depth: 2

When to Use Custom User Context
--------------------------------

Use custom user context when you need to:

- **Integrate with existing apps** - Your application already has User/UserRole models
- **Use external auth** - Integrate with OAuth, SAML, LDAP, or other providers
- **Support multi-tenant** - Different user models per tenant/organization
- **Custom authentication** - Use any authentication mechanism (session, token, header, etc.)

.. note::

   Without configuration, flask-more-smorest uses its built-in JWT-based ``User`` model.
   The custom user context system allows you to replace this with your own implementation.

Quick Start
-----------

Register your custom user class (and optionally a custom getter):

.. code-block:: python

   from flask_more_smorest.perms import register_user_class

   def my_get_user():
       from flask import session
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None

   # Register - everything else derives from this!
   register_user_class(MyUser, get_current_user=my_get_user)

That's it! No classes, no base class, no multiple methods to override.

The system automatically provides:

- ``get_current_user()`` - Calls your registered function or uses JWT
- ``get_current_user_id()`` - Extracts ``id`` attribute from your user
- ``is_current_user_admin()`` - Checks admin role via ``has_role()``
- ``is_current_user_superadmin()`` - Checks superadmin role via ``has_role()``
- JWT authentication - Loads instances of your user class (when no custom getter provided)

How It Works
-------------

The user context system is elegantly simple:

1. **Register** your user class with ``register_user_class()``
2. **Optionally provide** a custom getter (default: JWT-based)
3. **All other functions** automatically derive from your registration
4. **Your user object** just needs an ``id`` attribute and optional ``has_role()`` method

.. code-block:: python

   from flask_more_smorest.perms import (
       register_user_class,
       get_current_user,
       get_current_user_id,
       is_current_user_admin,
       is_current_user_superadmin,
   )

   def my_get_user():
       # Your custom logic to retrieve user
       user_id = request.headers.get('X-User-ID')
       return MyUser.query.get(user_id) if user_id else None

   register_user_class(MyUser, get_current_user=my_get_user)

   # Now you can use:
   user = get_current_user()          # Calls my_get_user()
   user_id = get_current_user_id()    # Extracts user.id
   admin = is_current_user_admin()    # Checks user.has_role('admin')
   superadmin = is_current_user_superadmin()  # Checks user.has_role('superadmin')

Flask-Login Integration
-------------------------

Integrate with Flask-Login's session-based authentication:

.. code-block:: python

   from flask_login import current_user
   from flask_more_smorest.perms import register_user_class

   def get_flask_login_user():
       return current_user if not current_user.is_anonymous else None

   register_user_class(MyUser, get_current_user=get_flask_login_user)

   # Now all permission checks use Flask-Login's current_user
   from flask_more_smorest.perms import is_current_user_admin

   @app.route('/api/admin/dashboard')
   def admin_dashboard():
       if is_current_user_admin():
           return "Admin dashboard"
       return "Access denied", 403

Benefits:

- Seamless Flask-Login integration
- Anonymous user handling via ``current_user.is_anonymous``
- Session-based authentication with all Flask-Login features

Custom JWT Implementation
-------------------------

If you have a custom JWT implementation:

.. code-block:: python

   import jwt
   from flask import request
   from flask_more_smorest.perms import register_user_class

   def decode_token():
       token = request.headers.get('Authorization', '').replace('Bearer ', '')
       try:
           return jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
       except jwt.InvalidTokenError:
           return None

   def get_jwt_user():
       payload = decode_token()
       if payload:
           return MyUser.query.get(payload.get('user_id'))
       return None

   register_user_class(MyUser, get_current_user=get_jwt_user)

OAuth Integration (Google, GitHub, etc.)
-----------------------------------------

.. code-block:: python

   from authlib.integrations.flask_client import OAuth
   from flask import session
   from flask_more_smorest.perms import register_user_class

   oauth = OAuth()

   google = oauth.register(
       'google',
       client_id='your-client-id',
       client_secret='your-client-secret',
       server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
       client_kwargs={'scope': 'openid email profile'}
   )

   def get_oauth_user():
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None

   register_user_class(MyUser, get_current_user=get_oauth_user)

   # OAuth callback handler
   @app.route('/auth/google/callback')
   def google_callback():
       token = google.authorize_access_token()
       user_info = google.parse_id_token(token)
       # Link/create user in your DB
       user = MyUser.get_or_create_from_oauth(user_info)
       session['user_id'] = user.id
       return redirect('/dashboard')

SAML Integration
----------------

.. code-block:: python

   from flask_saml2 import SP as SAMLSP
   from flask import session
   from flask_more_smorest.perms import register_user_class

   saml = SAMLSP(...)

   def get_saml_user():
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None

   register_user_class(MyUser, get_current_user=get_saml_user)

   # SAML assertion consumer service
   @app.route('/saml/acs')
   def saml_acs():
       authn_response = saml.parse_authn_request_response(request.form)
       user = MyUser.get_or_create_from_saml(authn_response)
       session['user_id'] = user.id
       return redirect('/dashboard')

LDAP Integration
----------------

.. code-block:: python

   from flask import session
   from flask_more_smorest.perms import register_user_class
   import ldap3

   def get_ldap_user():
       username = session.get('username')
       if not username:
           return None

       # Look up user in LDAP
       server = ldap3.Server(app.config['LDAP_SERVER'])
       conn = ldap3.Connection(server, 'uid=' + username + ',ou=users,dc=example,dc=com', password=...)

       if not conn.bind():
           return None

       # Sync to local DB if needed
       user = MyUser.get_or_create_from_ldap(username)
       return user

   register_user_class(MyUser, get_current_user=get_ldap_user)

Multi-Tenant Applications
-------------------------

Different user models per tenant:

.. code-block:: python

   from flask import g
   from flask_more_smorest.perms import register_user_class

   def get_tenant_user_model(tenant_id: str):
       """Get the User model class for a specific tenant."""
       module = import_module(f'tenants.{tenant_id}.models')
       return module.User

   def get_tenant_user():
       if not hasattr(g, 'tenant_id'):
           return None

       UserClass = get_tenant_user_model(g.tenant_id)
       user_id = session.get('user_id')
       return UserClass.query.get(user_id) if user_id else None

   register_user_class(get_tenant_user_model(g.tenant_id), get_current_user=get_tenant_user)

   # Tenant middleware
   @app.before_request
   def set_tenant():
       g.tenant_id = request.headers.get('X-Tenant-ID', 'default')

Type Safety with UserProtocol
------------------------------

Use ``UserProtocol`` for runtime type checking:

.. code-block:: python

   from flask_more_smorest.perms import UserProtocol, get_current_user, ROLE_ADMIN, ROLE_SUPERADMIN
   from typing import runtime_checkable

   @runtime_checkable
   class MyUser(UserProtocol):
       id: uuid.UUID
       email: str

       def has_role(self, role: str) -> bool:
           return self.role == role

       def list_roles(self) -> list[str]:
           return [self.role] if self.role else []

   # Now runtime checking works
   user = get_current_user()
   if isinstance(user, UserProtocol):
       print(f"User {user.email} is compliant with UserProtocol")
   else:
       print("Warning: User model doesn't implement UserProtocol")


Custom Role Checking
--------------------

If your custom User model has a different role system:

.. code-block:: python

   def get_custom_role_user():
       # Your custom user retrieval
       user_id = session.get('user_id')
       return MyUser.query.get(user_id) if user_id else None

   register_user_class(MyUser, get_current_user=get_custom_role_user)

   # Your User model just needs role properties:
   class MyUser:
       id: uuid.UUID
       roles: list[Role]

       @property
       def is_admin(self) -> bool:
           # Custom role checking - e.g., multiple admin levels
           return any(role.level >= 2 for role in self.roles)

       @property
       def is_superadmin(self) -> bool:
           # Custom superadmin check
           return any(role.level >= 3 for role in self.roles)

User Object Requirements
------------------------

Your user object must have:

**Required:**

- ``id``: Any type (UUID, int, string are all supported)

**Optional (for admin checks):**

- ``is_admin`` property/method: Returns ``True`` if user has admin privileges
- ``is_superadmin`` property/method: Returns ``True`` if user has superadmin privileges

The system handles:

- **Dict-style access**: ``{'id': uuid.uuid4(), 'is_admin': True}``
- **Object attribute access**: ``user.id``, ``user.is_admin``
- **Property access**: ``user.is_admin`` (calls ``@property`` decorated method)
- **Method access**: ``user.is_admin()`` (calls callable)

Testing with Custom Context
----------------------------

Clear registration in tests:

.. code-block:: python

   from flask_more_smorest.perms import register_user_class, clear_registration

   def test_with_custom_user():
       # Register mock user
       class MockUser:
           id = 'test-id'

           def has_role(self, role: str) -> bool:
               return role == 'admin'

           def list_roles(self) -> list[str]:
               return ['admin']

       register_user_class(MockUser)

       # Test your code
       user = get_current_user()
       assert user.id == 'test-id'

       # Clear for next test
       clear_registration()


Troubleshooting
---------------

**User not showing up in error debug context:**

- Ensure your registered function returns a user with an ``id`` attribute
- Verify debug mode is enabled (``app.config['DEBUG'] = True``)

**Permission checks failing unexpectedly:**

- Verify ``is_admin`` and ``is_superadmin`` are accessible as properties on your user object
- Check that user ID is being returned correctly
- Ensure request context exists when calling permission methods

**"User has no attribute 'is_admin'" error:**

- Add ``@property`` decorator to your role-checking methods
- Ensure default ``False`` return when role not found:

  .. code-block:: python

     @property
     def is_admin(self) -> bool:
         return getattr(self, '_is_admin', False)

**Clearing registration for tests:**

.. code-block:: python

   from flask_more_smorest.perms import clear_registration

   def setup():
       clear_registration()

**Getting the default JWT behavior back:**

.. code-block:: python

   from flask_more_smorest.perms import clear_registration

   # Revert to built-in JWT authentication
   clear_registration()

.. seealso::

   :doc:`user-extension`
      Comprehensive guide for extending User models.

   :doc:`permissions`
      Learn about the permission system and how it works with user context.
