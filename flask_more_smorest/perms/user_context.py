"""Configurable user context for flask-more-smorest.

Simple function-based registration system with type enforcement.

**Quick Start:**

For most use cases with flask-more-smorest's built-in User model,
no configuration is needed. Just use the class method:

    .. code-block:: python

        from flask_more_smorest import User

        user = User.get_current_user()  # Returns User | None

For custom User models or external auth systems, register your user class
(and optionally a custom getter):

    .. code-block:: python

        from flask_more_smorest.perms import register_user_class

        def my_get_user():
            from flask import session

            user_id = session.get("user_id")
            return MyUser.query.get(user_id) if user_id else None

        # Register - everything else derives from this!
        register_user_class(MyUser, get_current_user=my_get_user)

        # Now use the class method for typed access
        user = MyUser.get_current_user()  # Returns MyUser | None

**That's it!** No classes, no ABC, no multiple methods to override.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeVar, cast, overload, runtime_checkable

from flask import current_app, has_app_context

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapped

logger = logging.getLogger(__name__)

# Admin role type - constrained to valid admin roles only
AdminRole = Literal["admin", "superadmin"]

# Role constants
ROLE_ADMIN: AdminRole = "admin"
ROLE_SUPERADMIN: AdminRole = "superadmin"


@runtime_checkable
class UserProtocol(Protocol):
    """User interface required by the permissions system."""

    @property
    def id(self) -> uuid.UUID | Mapped[uuid.UUID]:
        """Return the user's identifier."""
        ...

    def has_role(self, role: AdminRole) -> bool:
        """Check if user has the specified role."""
        ...

    def list_roles(self) -> list[str]:
        """List user roles as strings."""
        ...


# TypeVar for generic user functions
UserT = TypeVar("UserT", bound=UserProtocol)

# Type for user context function
GetCurrentUserFunc = Callable[[], UserProtocol | None]

# Global registration (fallback when no app context)
_get_current_user_func: GetCurrentUserFunc | None = None
_registered_user_class: type[UserProtocol] | None = None

_USER_CONTEXT_STATE_KEY = "user_context"


def _get_app_state() -> dict[str, Any]:
    extensions_state = current_app.extensions.setdefault("flask-more-smorest", {})
    return cast(
        dict[str, Any],
        extensions_state.setdefault(
            _USER_CONTEXT_STATE_KEY,
            {"get_current_user_func": None, "user_class": None},
        ),
    )


def _get_state() -> tuple[dict[str, Any], bool]:
    if has_app_context():
        return _get_app_state(), True

    return {
        "get_current_user_func": _get_current_user_func,
        "user_class": _registered_user_class,
    }, False


def register_user_class(
    user_cls: type[UserT],
    *,
    get_current_user: Callable[[], UserT | None] | None = None,
) -> None:
    """Register a custom user class for the application.

    This is the primary customization point. All user-related functionality
    (JWT authentication, permissions, etc.) will use this class.

    Args:
        user_cls: User subclass to use throughout the application
        get_current_user: Optional custom getter function.
            If provided, uses this instead of JWT.
            If not provided, JWT will load instances of user_cls.

    Example:

    .. code-block:: python

        class MyUser(User):
            employee_id = mapped_column(db.String(50))

        # Use JWT authentication with MyUser
        register_user_class(MyUser)

        # Or provide custom getter
        def my_get_user() -> MyUser | None:
            ...

        register_user_class(MyUser, get_current_user=my_get_user)
    """
    state, is_app_state = _get_state()
    state["user_class"] = user_cls
    if get_current_user is not None:
        state["get_current_user_func"] = get_current_user

    if not is_app_state:
        global _get_current_user_func, _registered_user_class  # noqa: PLW0603
        _registered_user_class = user_cls
        if get_current_user is not None:
            _get_current_user_func = get_current_user


@overload
def get_current_user() -> UserProtocol | None: ...


@overload
def get_current_user(user_type: type[UserT]) -> UserT | None: ...


def get_current_user(user_type: type[UserT] | None = None) -> UserProtocol | None:
    """Get the current authenticated user.

    **Preferred approach:** Use the class method on your User subclass:

        .. code-block:: python

            from flask_more_smorest import User

            # Untyped access
            user = User.get_current_user()

            # Typed access with custom user class
            class MyUser(User):
                employee_id = mapped_column(db.String(32))

            user = MyUser.get_current_user()  # Returns MyUser | None

    This module-level function is useful for advanced use cases where you need to:
    - Dynamically determine the user class at runtime
    - Test custom getter registration
    - Work with UserProtocol without knowing the concrete type

    Resolution order:
    1. Registered custom getter (via register_user_class)
    2. Default: JWT-based authentication (built-in)

    Args:
        user_type: Optional user class for typed return.
            If None, returns UserProtocol | None.

    Returns:
        Current user instance if authenticated, None otherwise
    """
    state, _ = _get_state()
    get_user_func = cast(GetCurrentUserFunc | None, state.get("get_current_user_func"))

    if get_user_func is not None:
        user = get_user_func()
    else:
        # Fall back to built-in JWT authentication
        from .models import _get_jwt_current_user

        user = _get_jwt_current_user()

    if user_type is not None:
        if user is None:
            return None
        if not isinstance(user, user_type):
            return None
        return user

    return user


def _get_registered_user_class() -> type[UserProtocol] | None:
    """Get the registered user class (internal helper).

    Returns:
        Registered User subclass or None if not registered
    """
    state, _ = _get_state()
    return state.get("user_class")


def get_current_user_id() -> uuid.UUID | None:
    """Get the current authenticated user's ID.

    Automatically extracts the `id` attribute from the result of `get_current_user()`.
    Handles both UUID and Mapped[UUID] types.

    Returns:
        Current user's UUID if authenticated, None otherwise
    """
    user = get_current_user()
    if user is None:
        return None

    user_id = getattr(user, "id", None)
    if user_id is None:
        return None

    # Handle Mapped[UUID] by extracting the value
    try:
        from sqlalchemy.orm.attributes import InstrumentedAttribute

        if isinstance(user_id, InstrumentedAttribute):
            return cast(uuid.UUID, user_id.property.class_.impl.type.python_type(user_id))
    except Exception:  # nosec: B110  # Intentionally swallow errors during type checking
        pass

    return cast(uuid.UUID, user_id)


def is_current_user_admin() -> bool:
    """Check if the current user is an admin.

    Uses the user's role-based access via `has_role`.

    Returns:
        True if current user is admin, False otherwise
    """
    user = get_current_user()
    if user is None:
        return False

    return bool(user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))


def is_current_user_superadmin() -> bool:
    """Check if the current user is a superadmin.

    Uses the user's role-based access via `has_role`.

    Returns:
        True if current user is superadmin, False otherwise
    """
    user = get_current_user()
    if user is None:
        return False

    return bool(user.has_role(ROLE_SUPERADMIN))


def clear_registration() -> None:
    """Clear the custom user registration.

    Clears both the custom get_current_user function and the registered user class,
    resetting to default JWT authentication with base User model.

    Useful for testing to reset to default behavior.

    Example:

        .. code-block:: python

            def test_with_custom_user():
                register_user_class(MyUser)
                # ... test ...
                clear_registration()  # Reset for next test
    """
    state, is_app_state = _get_state()
    state["get_current_user_func"] = None
    state["user_class"] = None

    if not is_app_state:
        global _get_current_user_func, _registered_user_class  # noqa: PLW0603
        _get_current_user_func = None
        _registered_user_class = None
