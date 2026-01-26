"""User context helpers for flask-more-smorest.

This module exposes runtime user lookup helpers and role checks.
All configuration is driven through ``init_fms`` in ``user_registry``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Literal, TypeVar, cast, overload

# Admin role type - constrained to valid admin roles only
AdminRole = Literal["ADMIN", "SUPERADMIN"]

# Role constants - uppercase values
ROLE_ADMIN: AdminRole = "ADMIN"
ROLE_SUPERADMIN: AdminRole = "SUPERADMIN"

if TYPE_CHECKING:
    from .models.abstract_user import AbstractUser

    GetCurrentUserFunc = Callable[[], AbstractUser | None]
else:  # pragma: no cover - runtime placeholder
    AbstractUser = object  # type: ignore[assignment]
    GetCurrentUserFunc = Callable[[], object | None]  # type: ignore[assignment]

UserT = TypeVar("UserT", bound="AbstractUser")


@overload
def get_current_user() -> AbstractUser | None: ...


@overload
def get_current_user(user_type: type[UserT]) -> UserT | None: ...


def get_current_user(user_type: type[UserT] | None = None) -> UserT | AbstractUser | None:
    """Get the current authenticated user.

    Resolution order:
    1. Registered custom getter (via init_fms)
    2. Default: JWT-based authentication (built-in)

    Args:
        user_type: Optional user class for typed return.
            If None, returns AbstractUser | None.

    Returns:
        Current user instance if authenticated, None otherwise
    """
    from .user_registry import get_current_user_func

    get_user_func = get_current_user_func()

    if get_user_func is not None:
        user = get_user_func()
    else:
        # Fall back to built-in JWT authentication
        from flask_jwt_extended import current_user as jwt_current_user
        from flask_jwt_extended import exceptions, verify_jwt_in_request

        try:
            verify_jwt_in_request()
        except exceptions.JWTExtendedException:
            return None
        except Exception:
            return None

        try:
            return cast("AbstractUser | None", jwt_current_user._get_current_object())
        except (AttributeError, RuntimeError):
            return None

    if user_type is not None:
        if user is None:
            return None
        if not isinstance(user, user_type):
            return None
        # Explicit cast to help mypy's incremental mode understand the narrowing
        return cast(UserT, user)  # type: ignore[redundant-cast]

    return user


def get_current_user_id() -> uuid.UUID | None:
    """Get the current authenticated user's ID."""
    user = get_current_user()
    if user is None:
        return None

    user_id = getattr(user, "id", None)
    if user_id is None:
        return None

    # Handle Mapped[UUID] by extracting the value
    with suppress(Exception):
        from sqlalchemy.orm.attributes import InstrumentedAttribute

        if isinstance(user_id, InstrumentedAttribute):
            return cast(uuid.UUID, user_id.property.class_.impl.type.python_type(user_id))

    return cast(uuid.UUID, user_id)


def is_current_user_admin() -> bool:
    """Check if the current user is an admin."""
    user = get_current_user()
    if user is None:
        return False

    return bool(user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))


def is_current_user_superadmin() -> bool:
    """Check if the current user is a superadmin."""
    user = get_current_user()
    if user is None:
        return False

    return bool(user.has_role(ROLE_SUPERADMIN))
