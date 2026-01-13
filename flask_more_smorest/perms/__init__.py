"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.
"""

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
from .perms_blueprint import PermsBlueprint, PermsBlueprintMixin
from .user_blueprints import UserBlueprint
from .user_context import (
    UserProtocol,
    register_get_current_user,
    register_get_current_user_id,
    register_is_current_user_admin,
    register_is_current_user_superadmin,
)

# Type stubs for lazy-loaded objects
if TYPE_CHECKING:
    from flask_smorest import Blueprint as _Blueprint

    from .user_models import (
        DefaultUserRole,
        Domain,
        Token,
        User,
        UserRole,
        UserSetting,
        get_current_user,
        get_current_user_id,
    )
    from .user_schemas import UserSchema

    user_bp: _Blueprint

# Lazy imports for models and schemas to avoid premature table creation
# These are imported on first access via __getattr__
__all__ = [
    "Api",
    "BasePermsModel",
    "user_bp",
    "User",
    "UserRole",
    "Domain",
    "Token",
    "UserSetting",
    "DefaultUserRole",
    "UserSchema",
    "get_current_user",
    "get_current_user_id",
    "HasUserMixin",
    "UserOwnershipMixin",
    "ProfileMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "PermsBlueprintMixin",
    "PermsBlueprint",
    "UserBlueprint",
    "init_jwt",
    # User context configuration
    "register_get_current_user",
    "register_get_current_user_id",
    "register_is_current_user_admin",
    "register_is_current_user_superadmin",
    "UserProtocol",
]


def __getattr__(name: str) -> object:
    """Lazy import user models and schemas to avoid premature table creation."""
    if name == "user_bp":
        from . import user_blueprints

        return user_blueprints.user_bp

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
        "get_current_user",
        "get_current_user_id",
    ):
        from .user_models import (
            DefaultUserRole,
            Domain,
            Token,
            User,
            UserRole,
            UserSetting,
            get_current_user,
            get_current_user_id,
        )

        # Cache the imports
        globals()[name] = locals()[name]
        return locals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
