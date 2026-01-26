Testing Guide
=============

Flask-More-Smorest provides testing helpers to simplify testing authenticated
endpoints and permission-based views.

.. contents:: Table of Contents
   :local:
   :depth: 2

Testing Helpers
---------------

The :mod:`flask_more_smorest.testing` module provides context managers and utility
functions to simplify testing with JWT authentication.

Context Managers
~~~~~~~~~~~~~~~~

``as_user(client, user_id, additional_claims=None)``
  Context manager to set JWT authentication for a user in test requests.

``as_admin(client, user_id, additional_claims=None, roles=None)``
  Context manager to set JWT authentication for an admin user in test requests.

Utility Functions
~~~~~~~~~~~~~~~~~

``clear_registration()``
  Clear the custom user registration, resetting to default JWT behavior.

Quick Start
-----------

Testing authenticated endpoints:

.. code-block:: python

    import pytest
    from flask_more_smorest.perms.models.defaults import User
    from flask_more_smorest.testing import as_user

    def test_get_my_profile(client, db_session):
        # Create test user
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Test authenticated endpoint
        with as_user(client, str(user.id)):
            response = client.get("/api/users/me/")
            assert response.status_code == 200
            assert response.json["email"] == "test@example.com"

Testing admin-only endpoints:

.. code-block:: python

    import pytest
    from flask_more_smorest.perms.models.defaults import User, UserRole, BaseRoleEnum
    from flask_more_smorest.testing import as_admin

    def test_admin_endpoint(client, db_session):
        # Create admin user
        with User.bypass_perms():
            admin = User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.ADMIN))

        # Test admin-only endpoint
        with as_admin(client, str(admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

Testing superadmin endpoints:

.. code-block:: python

    def test_superadmin_endpoint(client, db_session):
        with User.bypass_perms():
            admin = User(email="superadmin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.SUPERADMIN))

        with as_admin(client, str(admin.id), roles=["superadmin"]):
            response = client.delete("/api/users/123/")
            assert response.status_code == 204

As User Context Manager
-----------------------

.. py:function:: as_user(client, user_id, additional_claims=None)

   Context manager to set JWT authentication for a user in test requests.

   :param FlaskClient client: Flask test client
   :param str user_id: User ID to authenticate as (string representation of UUID)
   :param dict additional_claims: Optional additional JWT claims to include in the token

   Example:

   .. code-block:: python

       with as_user(client, str(user.id), additional_claims={"custom_claim": "value"}):
           response = client.get("/api/users/me/")
           # Token will include custom_claim

As Admin Context Manager
-------------------------

.. py:function:: as_admin(client, user_id, additional_claims=None, roles=None)

   Context manager to set JWT authentication for an admin user in test requests.

   This is a convenience wrapper around :func:`as_user` that automatically adds
   admin role claims to the JWT token.

   :param FlaskClient client: Flask test client
   :param str user_id: Admin user ID to authenticate as (string representation of UUID)
   :param dict additional_claims: Optional additional JWT claims to include in the token
   :param list roles: List of roles to assign (default: ["admin"]). Use ["superadmin"]
       for superadmin privileges.

   Example:

   .. code-block:: python

       # Default admin role
       with as_admin(client, str(admin.id)):
           response = client.get("/api/users/")

       # Superadmin role
       with as_admin(client, str(admin.id), roles=["superadmin"]):
           response = client.delete("/api/users/123/")

Clear Registration
------------------

.. py:function:: clear_registration()

   Clear the custom user registration.

   This is a proxy to :func:`flask_more_smorest.perms.user_context.clear_registration`
   for convenience in test files.

   Useful for testing to reset to default JWT behavior after registering
   custom user classes or getters.

   Example:

   .. code-block:: python

       from flask_more_smorest.testing import clear_registration, init_fms

       def test_with_custom_user():
           init_fms(user=MyUser)
           # ... test ...
           clear_registration()  # Reset for next test

Testing with Fixtures
---------------------

Create reusable test fixtures:

.. code-block:: python

    import pytest
    from flask_more_smorest.perms.models.defaults import User, UserRole, BaseRoleEnum
    from flask_more_smorest.testing import as_user, as_admin

    @pytest.fixture
    def test_user(db_session):
        """Create a test user."""
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()
        return user

    @pytest.fixture
    def test_admin(db_session):
        """Create an admin user."""
        with User.bypass_perms():
            admin = User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.ADMIN))
        return admin

    def test_authenticated_endpoint(client, test_user):
        """Test authenticated endpoint with fixture."""
        with as_user(client, str(test_user.id)):
            response = client.get("/api/users/me/")
            assert response.status_code == 200

    def test_admin_endpoint(client, test_admin):
        """Test admin endpoint with fixture."""
        with as_admin(client, str(test_admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

Testing Permissions
-------------------

Test permission-based access control:

.. code-block:: python

    from flask_more_smorest import BasePermsModel
    from flask_more_smorest.testing import as_user, as_admin
    from flask_more_smorest.sqla import db
    from sqlalchemy.orm import Mapped, mapped_column

    class Article(BasePermsModel):
        title: Mapped[str] = mapped_column(db.String(100))
        content: Mapped[str] = mapped_column(db.Text)
        is_public: Mapped[bool] = mapped_column(db.Boolean, default=False)

        def _can_read(self, current_user) -> bool:
            if self.is_public:
                return True
            return self.user_id == current_user.id if current_user else False

        def _can_write(self, current_user) -> bool:
            if not current_user:
                return False
            return self.user_id == current_user.id or current_user.is_admin

    def test_article_permissions(client, db_session):
        with Article.bypass_perms():
            owner = User(email="owner@example.com", password="password123")
            owner.save()

            admin = User(email="admin@example.com", password="password123")
            admin.save()

            public_article = Article(title="Public", content="Content", is_public=True)
            public_article.save()

            private_article = Article(title="Private", content="Secret", is_public=False, user_id=owner.id)
            private_article.save()

        # Unauthenticated: can read public, not private
        response = client.get(f"/api/articles/{public_article.id}/")
        assert response.status_code == 200

        response = client.get(f"/api/articles/{private_article.id}/")
        assert response.status_code == 403

        # Owner can read private article
        with as_user(client, str(owner.id)):
            response = client.get(f"/api/articles/{private_article.id}/")
            assert response.status_code == 200

        # Admin can read all articles
        with as_admin(client, str(admin.id)):
            response = client.get(f"/api/articles/{private_article.id}/")
            assert response.status_code == 200

Testing Custom User Context
----------------------------

When using custom user context (see :doc:`custom-user-context`), use ``clear_registration()``
to reset between tests:

.. code-block:: python

    from flask_more_smorest.testing import clear_registration, init_fms
    from flask_more_smorest.perms import get_current_user

    class MockUser:
        id = "test-id"

        def has_role(self, role: str) -> bool:
            return role == "admin"

        def list_roles(self) -> list[str]:
            return ["admin"]

    def test_with_custom_user():
        # Register mock user
        init_fms(user=MockUser)

        # Test your code
        user = get_current_user()
        assert user.id == "test-id"

        # Clear for next test
        clear_registration()

    def test_with_default_jwt():
        # Clear to get back default JWT behavior
        clear_registration()

        # Now use default User model
        user = User(email="test@example.com", password="password123")
        user.save()

        with as_user(client, str(user.id)):
            response = client.get("/api/users/me/")
            assert response.status_code == 200

Common Patterns
---------------

Test multiple roles:

.. code-block:: python

    def test_role_based_access(client, db_session):
        with User.bypass_perms():
            regular = User(email="regular@example.com", password="password123")
            regular.save()

            admin = User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.ADMIN))

            superadmin = User(email="superadmin@example.com", password="password123")
            superadmin.save()
            superadmin.roles.append(UserRole(user=superadmin, role=BaseRoleEnum.SUPERADMIN))

        # Regular user: 403 on admin endpoint
        with as_user(client, str(regular.id)):
            response = client.get("/api/users/")
            assert response.status_code == 403

        # Admin: 200 on admin endpoint
        with as_admin(client, str(admin.id)):
            response = client.get("/api/users/")
            assert response.status_code == 200

        # Superadmin: can delete
        with as_admin(client, str(superadmin.id), roles=["superadmin"]):
            response = client.delete(f"/api/users/{regular.id}/")
            assert response.status_code == 204

Test with additional claims:

.. code-block:: python

    def test_custom_claims(client, db_session):
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        # Test endpoint that reads custom claims
        with as_user(client, str(user.id), additional_claims={"tenant_id": "12345"}):
            response = client.get("/api/users/me/")
            assert response.status_code == 200
            # Endpoint can now access tenant_id from JWT claims

Test multiple requests in one context:

.. code-block:: python

    def test_multiple_authenticated_requests(client, db_session):
        with User.bypass_perms():
            user = User(email="test@example.com", password="password123")
            user.save()

        with as_user(client, str(user.id)):
            # All requests in this block are authenticated
            response1 = client.get("/api/users/me/")
            assert response1.status_code == 200

            response2 = client.get("/api/users/")
            assert response2.status_code == 200

            response3 = client.patch("/api/users/me/", json={"email": "new@example.com"})
            assert response3.status_code == 200

.. seealso::

   :doc:`custom-user-context`
      Guide for integrating with external authentication systems.

   :doc:`permissions`
      Learn about the permission system and how it works with user context.
