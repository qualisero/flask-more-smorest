"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.

**Quick Start:**

    from flask_more_smorest.perms import init_fms
    from flask_more_smorest.perms.models.defaults import User

    # Register user models
    init_fms(user=User)

    # Use the UserBlueprint
    user_bp = UserBlueprint(register=False)
    api.register_blueprint(user_bp)

    # Note: no global singleton user_bp is provided; create explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .api import Api
from .base_perms_model import BasePermsModel
from .jwt import init_jwt
from .model_mixins import (
    HasUserMixin,
    ProfileMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UserOwnershipMixin,
)
from .models import AbstractDomain, AbstractToken, AbstractUser, AbstractUserRole, AbstractUserSetting
from .perms_blueprint import PermsBlueprint, PermsBlueprintMixin
from .user_blueprint import UserBlueprint
from .user_context import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    AdminRole,
    get_current_user,
    get_current_user_id,
    is_current_user_admin,
    is_current_user_superadmin,
)
from .user_registry import clear_registration as _clear_registration
from .user_registry import get_current_user_func, init_fms

if TYPE_CHECKING:
    from .user_blueprint import UserBlueprint


def __getattr__(name: str) -> object:
    """Lazy attribute access for schemas."""

    if TYPE_CHECKING:
        from .user_schemas import UserSchema

    if name == "UserSchema":
        from .user_schemas import UserSchema

        globals()["UserSchema"] = UserSchema
        return UserSchema

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def clear_registration() -> None:
    """Clear all user model registrations and helper functions."""
    _clear_registration()


__all__ = [
    "ROLE_ADMIN",
    "ROLE_SUPERADMIN",
    "AbstractDomain",
    "AbstractToken",
    # Abstract models
    "AbstractUser",
    "AbstractUserRole",
    "AbstractUserSetting",
    # User context
    "AdminRole",
    "Api",
    "BasePermsModel",
    "HasUserMixin",
    "PermsBlueprint",
    "PermsBlueprintMixin",
    "ProfileMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UserBlueprint",
    "UserOwnershipMixin",
    "UserSchema",
    "clear_registration",
    "get_current_user",
    "get_current_user_func",
    "get_current_user_id",
    # User registry
    "init_fms",
    "init_jwt",
    "is_current_user_admin",
    "is_current_user_superadmin",
]
