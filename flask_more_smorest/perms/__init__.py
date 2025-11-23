"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.
"""

from .api import Api
from .base_perms_model import BasePermsModel as BaseModel
from .user_models import User, UserRole, Domain, Token, UserSetting, current_user, get_current_user_id
from .perms_blueprint import PermsBlueprintMixin

from ..crud import CRUDBlueprint as CRUDBlueprintBase


class CRUDBlueprint(CRUDBlueprintBase, PermsBlueprintMixin):
    """CRUD Blueprint with permission annotations.

    Combines CRUDBlueprint functionality with PermsBlueprintMixin to provide
    automatic CRUD operations with permission checking support.
    """

    pass


__all__ = [
    "Api",
    "BaseModel",
    "User",
    "UserRole",
    "Domain",
    "Token",
    "UserSetting",
    "current_user",
    "get_current_user_id",
    "PermsBlueprintMixin",
    "CRUDBlueprint",
]
