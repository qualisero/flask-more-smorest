"""Testing helpers for Flask-More-Smorest.

Provides context managers and utility functions to simplify testing
authenticated endpoints and permission-based views.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask.testing import FlaskClient

__all__ = ["as_admin", "as_user", "clear_registration"]


def clear_registration() -> None:
    """Clear the custom user registration.

    This is a proxy to :func:`flask_more_smorest.perms.clear_registration`
    for convenience in test files.

    Useful for testing to reset to default JWT behavior after registering
    custom user classes or getters.

    Example:

    .. code-block:: python

        from flask_more_smorest.testing import clear_registration
        from flask_more_smorest.perms import init_fms

        def test_with_custom_user():
            init_fms(user=MyUser)
            # ... test ...
            clear_registration()  # Reset for next test
    """
    from .perms.user_registry import clear_registration as _clear_registration

    _clear_registration()


@contextmanager
def as_user(
    client: FlaskClient, user_id: str, additional_claims: dict[str, Any] | None = None
) -> Generator[None, None, None]:
    """Context manager to set JWT authentication for a user in test requests.

    This simplifies testing authenticated endpoints by automatically setting
    the JWT token in request headers.

    Args:
        client: Flask test client
        user_id: User ID to authenticate as (string representation of UUID)
        additional_claims: Optional additional JWT claims to include in the token

    Yields:
        None

    Example:

    .. code-block:: python

        from flask_more_smorest import User
        from flask_more_smorest.testing import as_user

        def test_get_my_profile(client, db_session):
            # Create test user
            user = User(email="test@example.com", password="password123")
            user.save()

            # Test authenticated endpoint
            with as_user(client, str(user.id)):
                response = client.get("/api/users/me/")
                assert response.status_code == 200
                assert response.json["email"] == "test@example.com"

    Example with additional claims:

    .. code-block:: python

        with as_user(client, str(user.id), additional_claims={"custom_claim": "value"}):
            response = client.get("/api/users/me/")
            # Token will include custom_claim

    Note:
        This context manager sets client.environ_base with the authorization header.
        The Flask test client will include these headers in all requests made
        within the context.
    """
    from flask_jwt_extended import create_access_token

    # Create token with user identity
    token = create_access_token(identity=user_id, additional_claims=additional_claims or {})

    # Set authorization header for all requests within context
    # Note: Flask test client environ_base uses HTTP_ prefix for headers
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # Save original environ_base and set new one with auth header
    original_environ_base = client.environ_base
    client.environ_base = {**(original_environ_base or {}), **headers}

    try:
        yield
    finally:
        # Restore original environ_base
        client.environ_base = original_environ_base


@contextmanager
def as_admin(
    client: FlaskClient,
    user_id: str,
    additional_claims: dict[str, Any] | None = None,
    roles: list[str] | None = None,
) -> Generator[None, None, None]:
    """Context manager to set JWT authentication for an admin user in test requests.

    This is a convenience wrapper around :func:`as_user` that automatically adds
    admin role claims to the JWT token.

    Args:
        client: Flask test client
        user_id: Admin user ID to authenticate as (string representation of UUID)
        additional_claims: Optional additional JWT claims to include in the token
        roles: List of roles to assign (default: ["admin"]). Use ["superadmin"]
            for superadmin privileges.

    Yields:
        None

    Example:

    .. code-block:: python

        from flask_more_smorest import User
        from flask_more_smorest.testing import as_admin
        from flask_more_smorest.perms.models.defaults import UserRole, BaseRoleEnum

        def test_admin_endpoint(client, db_session):
            # Create admin user
            admin = User(email="admin@example.com", password="password123")
            admin.save()
            admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.ADMIN))

            # Test admin-only endpoint
            with as_admin(client, str(admin.id)):
                response = client.get("/api/users/")
                assert response.status_code == 200

    Example with superadmin:

    .. code-block:: python

        admin.roles.append(UserRole(user=admin, role=BaseRoleEnum.SUPERADMIN))

        with as_admin(client, str(admin.id), roles=["superadmin"]):
            response = client.delete("/api/users/123/")
            assert response.status_code == 204

    Note:
        This context manager sets client.environ_base with the authorization header.
        The Flask test client will include these headers in all requests made
        within the context.
    """
    from flask_jwt_extended import create_access_token

    # Merge roles into additional_claims
    merged_claims = {**(additional_claims or {}), "roles": roles or ["admin"]}

    # Create token with admin claims
    token = create_access_token(identity=user_id, additional_claims=merged_claims)

    # Set authorization header for all requests within context
    # Note: Flask test client environ_base uses HTTP_ prefix for headers
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # Save original environ_base and set new one with auth header
    original_environ_base = client.environ_base
    client.environ_base = {**(original_environ_base or {}), **headers}

    try:
        yield
    finally:
        # Restore original environ_base
        client.environ_base = original_environ_base
