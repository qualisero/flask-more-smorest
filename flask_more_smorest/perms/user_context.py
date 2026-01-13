"""Configurable user context for flask-more-smorest.

This module provides a pluggable system for user authentication context,
allowing applications to use their own User models while still leveraging
flask-more-smorest's permission system.

Configuration:
    Applications can configure custom user context providers via Flask config:

    ```python
    app.config['FMS_GET_CURRENT_USER'] = my_get_current_user
    app.config['FMS_GET_CURRENT_USER_ID'] = my_get_current_user_id
    app.config['FMS_IS_CURRENT_USER_ADMIN'] = my_is_admin_check
    app.config['FMS_IS_CURRENT_USER_SUPERADMIN'] = my_is_superadmin_check
    ```

    Or by calling the registration functions:

    ```python
    from flask_more_smorest.perms.user_context import (
        register_get_current_user,
        register_get_current_user_id,
        register_is_current_user_admin,
        register_is_current_user_superadmin,
    )

    register_get_current_user(my_get_current_user)
    register_is_current_user_superadmin(my_is_superadmin_check)
    ```
"""

import logging
import uuid
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

# Type for user context functions
GetCurrentUserFunc = Callable[[], Any]
GetCurrentUserIdFunc = Callable[[], uuid.UUID | None]
IsCurrentUserAdminFunc = Callable[[], bool]
IsCurrentUserSuperadminFunc = Callable[[], bool]

# Global registrations (used when no app context or config not set)
_global_get_current_user: GetCurrentUserFunc | None = None
_global_get_current_user_id: GetCurrentUserIdFunc | None = None
_global_is_current_user_admin: IsCurrentUserAdminFunc | None = None
_global_is_current_user_superadmin: IsCurrentUserSuperadminFunc | None = None


@runtime_checkable
class UserProtocol(Protocol):
    """Protocol defining the minimum interface for a User object.

    Applications using custom User models should ensure their User class
    implements these properties/methods for compatibility with the permission system.
    """

    id: uuid.UUID

    @property
    def is_admin(self) -> bool:
        """Whether the user has admin privileges (includes superadmin)."""
        ...

    @property
    def is_superadmin(self) -> bool:
        """Whether the user has superadmin privileges."""
        ...


def register_get_current_user(func: GetCurrentUserFunc) -> None:
    """Register a custom function to get the current user.

    Args:
        func: Function that returns the current user or None
    """
    global _global_get_current_user
    _global_get_current_user = func


def register_get_current_user_id(func: GetCurrentUserIdFunc) -> None:
    """Register a custom function to get the current user ID.

    Args:
        func: Function that returns the current user's UUID or None
    """
    global _global_get_current_user_id
    _global_get_current_user_id = func


def register_is_current_user_admin(func: IsCurrentUserAdminFunc) -> None:
    """Register a custom function to check if current user is admin.

    Args:
        func: Function that returns True if current user is admin
    """
    global _global_is_current_user_admin
    _global_is_current_user_admin = func


def register_is_current_user_superadmin(func: IsCurrentUserSuperadminFunc) -> None:
    """Register a custom function to check if current user is superadmin.

    Args:
        func: Function that returns True if current user is superadmin
    """
    global _global_is_current_user_superadmin
    _global_is_current_user_superadmin = func


def get_current_user() -> Any:
    """Get the current authenticated user.

    Resolution order:
    1. App config 'FMS_GET_CURRENT_USER' if set
    2. Globally registered function via register_get_current_user()
    3. Default: flask-more-smorest's built-in user_models.get_current_user

    Returns:
        Current user instance if authenticated, None otherwise
    """
    # Check app config first
    if has_app_context():
        config_func = current_app.config.get("FMS_GET_CURRENT_USER")
        if config_func is not None:
            return config_func()

    # Check global registration
    if _global_get_current_user is not None:
        return _global_get_current_user()

    # Fall back to built-in
    from .user_models import get_current_user as builtin_get_current_user

    return builtin_get_current_user()


def get_current_user_id() -> uuid.UUID | None:
    """Get the current authenticated user's ID.

    Resolution order:
    1. App config 'FMS_GET_CURRENT_USER_ID' if set
    2. Globally registered function via register_get_current_user_id()
    3. Default: flask-more-smorest's built-in user_models.get_current_user_id

    Returns:
        Current user's UUID if authenticated, None otherwise
    """
    # Check app config first
    if has_app_context():
        config_func = current_app.config.get("FMS_GET_CURRENT_USER_ID")
        if config_func is not None:
            result: uuid.UUID | None = config_func()
            return result

    # Check global registration
    if _global_get_current_user_id is not None:
        return _global_get_current_user_id()

    # Fall back to built-in
    from .user_models import get_current_user_id as builtin_get_current_user_id

    return builtin_get_current_user_id()


def is_current_user_admin() -> bool:
    """Check if the current user is an admin.

    Resolution order:
    1. App config 'FMS_IS_CURRENT_USER_ADMIN' if set
    2. Globally registered function via register_is_current_user_admin()
    3. Default: Check user.is_admin via get_current_user()

    Returns:
        True if current user is admin, False otherwise
    """
    # Check app config first
    if has_app_context():
        config_func = current_app.config.get("FMS_IS_CURRENT_USER_ADMIN")
        if config_func is not None:
            result: bool = config_func()
            return result

    # Check global registration
    if _global_is_current_user_admin is not None:
        return _global_is_current_user_admin()

    # Fall back to checking user.is_admin
    try:
        user = get_current_user()
        return bool(user and getattr(user, "is_admin", False))
    except Exception:
        return False


def is_current_user_superadmin() -> bool:
    """Check if the current user is a superadmin.

    Resolution order:
    1. App config 'FMS_IS_CURRENT_USER_SUPERADMIN' if set
    2. Globally registered function via register_is_current_user_superadmin()
    3. Default: Check user.is_superadmin via get_current_user()

    Returns:
        True if current user is superadmin, False otherwise
    """
    # Check app config first
    if has_app_context():
        config_func = current_app.config.get("FMS_IS_CURRENT_USER_SUPERADMIN")
        if config_func is not None:
            result: bool = config_func()
            return result

    # Check global registration
    if _global_is_current_user_superadmin is not None:
        return _global_is_current_user_superadmin()

    # Fall back to checking user.is_superadmin
    try:
        user = get_current_user()
        return bool(user and getattr(user, "is_superadmin", False))
    except Exception:
        return False


def clear_registrations() -> None:
    """Clear all global registrations. Useful for testing."""
    global \
        _global_get_current_user, \
        _global_get_current_user_id, \
        _global_is_current_user_admin, \
        _global_is_current_user_superadmin
    _global_get_current_user = None
    _global_get_current_user_id = None
    _global_is_current_user_admin = None
    _global_is_current_user_superadmin = None
