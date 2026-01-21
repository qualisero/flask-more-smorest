"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user_blueprint import UserBlueprint

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
from .perms_blueprint import PermsBlueprint, PermsBlueprintMixin
from .user_blueprint import UserBlueprint
from .user_context import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    AdminRole,
    UserProtocol,
    clear_registration,
    get_current_user,
    get_current_user_id,
    is_current_user_admin,
    is_current_user_superadmin,
    register_user_class,
)

_user_bp: UserBlueprint | None = None


def _get_default_user_bp() -> UserBlueprint:
    """Get or create the default user_bp instance."""
    global _user_bp
    if _user_bp is None:
        _user_bp = UserBlueprint()
    return _user_bp


def __getattr__(name: str) -> object:
    """Lazy attribute access for default user_bp instance and models/schemas."""
    if name == "user_bp":
        return _get_default_user_bp()

    # Type stubs for lazy-loaded objects
    if TYPE_CHECKING:
        from .models import (
            DefaultUserRole,
            Domain,
            Token,
            User,
            UserRole,
            UserSetting,
        )
        from .user_schemas import UserSchema

    # Lazy imports for models and schemas to avoid premature table creation
    if name == "UserSchema":
        from .user_schemas import UserSchema

        globals()["UserSchema"] = UserSchema
        return UserSchema

    if name in (
        "User",
        "UserRole",
        "Domain",
        "Token",
        "UserSetting",
        "DefaultUserRole",
    ):
        from .models import (
            DefaultUserRole,
            Domain,
            Token,
            User,
            UserRole,
            UserSetting,
        )

        # Cache the imports
        globals()[name] = locals()[name]
        return locals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Api",
    "BasePermsModel",
    "User",
    "UserRole",
    "Domain",
    "Token",
    "UserSetting",
    "DefaultUserRole",
    "UserSchema",
    "get_current_user",
    "get_current_user_id",
    "is_current_user_admin",
    "is_current_user_superadmin",
    "HasUserMixin",
    "UserOwnershipMixin",
    "ProfileMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "PermsBlueprintMixin",
    "PermsBlueprint",
    "UserBlueprint",
    "init_jwt",
    # User context
    "UserProtocol",
    "AdminRole",
    "ROLE_ADMIN",
    "ROLE_SUPERADMIN",
    "register_user_class",
    "clear_registration",
    "user_bp",
]
