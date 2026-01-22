"""Testing utilities for Flask-More-Smorest tests.

Provides helpers for testing permission-aware code without
complex setup or mocking.

Example:
    >>> from tests.testing_utils import as_user, as_admin

    >>> with as_user(test_user):
    ...     article.save()  # Uses test_user for permission checks

    >>> with as_admin():
    ...     admin_only_model.delete()  # Runs as mock admin
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    pass


@contextmanager
def as_user(user: Any) -> Generator[Any, None, None]:
    """Context manager to run code as a specific user.

    Temporarily replaces the current user getter function to return
    the provided user object. Useful for testing permission logic
    without requiring full authentication setup.

    Args:
        user: User instance or mock object with id attribute.
              Can be None to simulate unauthenticated state.

    Yields:
        The user object

    Example:
        >>> with as_user(test_user):
        ...     assert article.can_write() == True
    """
    from flask_more_smorest.perms.user_context import _get_state

    state, _ = _get_state()
    original_getter = state.get("get_current_user_func")

    state["get_current_user_func"] = lambda: user

    try:
        yield user
    finally:
        state["get_current_user_func"] = original_getter


def _create_mock_user(
    *,
    is_admin: bool = False,
    is_superadmin: bool = False,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock user object with the given attributes.

    Args:
        is_admin: Whether the mock user should have admin role
        is_superadmin: Whether the mock user should have superadmin role
        user_id: Optional UUID for the user, generates random if not provided

    Returns:
        MagicMock configured to behave like a User
    """
    mock_user = MagicMock()
    mock_user.id = user_id or uuid.uuid4()
    mock_user.is_admin = is_admin or is_superadmin
    mock_user.is_superadmin = is_superadmin

    def has_role(role: str) -> bool:
        # Case-insensitive role check for compatibility
        role_upper = role.upper() if isinstance(role, str) else role
        if role_upper == "SUPERADMIN":
            return is_superadmin
        if role_upper == "ADMIN":
            return is_admin or is_superadmin
        return False

    mock_user.has_role = has_role

    def list_roles() -> list[str]:
        roles = []
        if is_superadmin:
            roles.append("SUPERADMIN")
        if is_admin or is_superadmin:
            roles.append("ADMIN")
        if not roles:
            roles.append("USER")
        return roles

    mock_user.list_roles = list_roles

    return mock_user


@contextmanager
def as_admin(user_id: uuid.UUID | None = None) -> Generator[MagicMock, None, None]:
    """Context manager to run code as an admin user.

    Creates a mock admin user and sets it as the current user for the
    duration of the context.

    Args:
        user_id: Optional UUID for the mock admin user

    Yields:
        The mock admin user object

    Example:
        >>> with as_admin() as admin:
        ...     assert model.can_write() == True
        ...     print(admin.id)  # Access the mock's ID
    """
    mock_admin = _create_mock_user(is_admin=True, user_id=user_id)

    with as_user(mock_admin):
        yield mock_admin


@contextmanager
def as_superadmin(user_id: uuid.UUID | None = None) -> Generator[MagicMock, None, None]:
    """Context manager to run code as a superadmin user.

    Creates a mock superadmin user and sets it as the current user for the
    duration of the context.

    Args:
        user_id: Optional UUID for the mock superadmin user

    Yields:
        The mock superadmin user object

    Example:
        >>> with as_superadmin() as superadmin:
        ...     # Can perform any operation
        ...     admin_user.delete()
    """
    mock_superadmin = _create_mock_user(is_superadmin=True, user_id=user_id)

    with as_user(mock_superadmin):
        yield mock_superadmin


@contextmanager
def as_anonymous() -> Generator[None, None, None]:
    """Context manager to run code as an unauthenticated user.

    Sets the current user to None, simulating an unauthenticated request.

    Yields:
        None

    Example:
        >>> with as_anonymous():
        ...     assert model.can_read() == False  # If auth required
    """
    with as_user(None):
        yield
