"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.
"""

from ..crud import CRUDBlueprint as CRUDBlueprintBase
from .api import Api
from .base_perms_model import BasePermsModel as BaseModel
from .perms_blueprint import PermsBlueprintMixin
from ..blueprint_operationid import BlueprintOperationIdMixin
from .user_models import Domain, Token, User, UserRole, UserSetting, current_user, get_current_user_id


class CRUDBlueprint(CRUDBlueprintBase, PermsBlueprintMixin, BlueprintOperationIdMixin):
    """CRUD Blueprint with permission annotations.

    Combines CRUDBlueprint functionality with PermsBlueprintMixin and BlueprintOperationIdMixin
    to provide automatic CRUD operations with permission checking support and operationIds.
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
