"""User-related models for Flask-More-Smorest.

This module provides a clean re-export of all user-related models,
maintaining backward compatibility while organizing code into focused modules.
"""

from __future__ import annotations

from .role import DefaultUserRole, Domain, UserRole
from .setting import UserSetting
from .token import Token
from .user import User, _get_jwt_current_user, current_user

__all__ = [
    "User",
    "UserRole",
    "Domain",
    "Token",
    "UserSetting",
    "DefaultUserRole",
    "current_user",
    "_get_jwt_current_user",
]
