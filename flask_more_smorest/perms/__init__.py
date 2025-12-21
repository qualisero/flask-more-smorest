"""Permissions module for Flask-More-Smorest.

This module provides the permissions system including the Api with auth,
BasePermsModel with permission checks, user models, and PermsBlueprintMixin.
"""

from flask.views import MethodView
from marshmallow import Schema

from ..blueprint_operationid import BlueprintOperationIdMixin
from ..crud import CRUDBlueprint as CRUDBlueprintBase
from .api import Api
from .base_perms_model import BasePermsModel as BaseModel
from .jwt import init_jwt
from .perms_blueprint import PermsBlueprintMixin
from .user_models import Domain, Token, User, UserRole, UserSetting, current_user, get_current_user_id


class CRUDBlueprint(CRUDBlueprintBase, PermsBlueprintMixin, BlueprintOperationIdMixin):
    """CRUD Blueprint with permission annotations.

    Combines CRUDBlueprint functionality with PermsBlueprintMixin and BlueprintOperationIdMixin
    to provide automatic CRUD operations with permission checking support and operationIds.
    """

    def _configure_endpoint(
        self,
        view_cls: type[MethodView],
        method_name: str,
        docstring: str,
        method_config: dict[str, Schema | str | bool | object],
    ) -> None:
        # Call each mixin's implementation explicitly
        PermsBlueprintMixin._configure_endpoint(self, view_cls, method_name, docstring, method_config)
        CRUDBlueprintBase._configure_endpoint(self, view_cls, method_name, docstring, method_config)


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
    "init_jwt",
]
