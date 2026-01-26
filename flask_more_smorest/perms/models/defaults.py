"""Default concrete implementations of user-related models.

This module provides battery-included default implementations that:
- Create actual database tables
- Use consistent table names with the existing schema
- Only exist when explicitly imported

These are opt-in defaults that reference the standard concrete models
(User, UserRole, Domain, Token, UserSetting) from the models package.
For full customization, inherit from the abstract bases in abstract_*.py.

**Quick start:**

    from flask_more_smorest.perms import init_fms
    from flask_more_smorest.perms.models.defaults import DefaultUser

    # Register the defaults
    init_fms(user=DefaultUser)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_roles import BaseRoleEnum
    from .role import Domain, UserRole
    from .setting import UserSetting
    from .token import Token
    from .user import User

    DefaultUser = User
    DefaultDomain = Domain
    DefaultUserSetting = UserSetting
    DefaultToken = Token
    DefaultUserRole = UserRole

__all__ = [
    "BaseRoleEnum",
    "DefaultDomain",
    "DefaultToken",
    "DefaultUser",
    "DefaultUserRole",
    "DefaultUserSetting",
]


def __getattr__(name: str) -> object:
    if name == "DefaultUser":
        from .user import User as DefaultUser

        return DefaultUser
    if name == "DefaultDomain":
        from .role import Domain as DefaultDomain

        return DefaultDomain
    if name == "DefaultUserSetting":
        from .setting import UserSetting as DefaultUserSetting

        return DefaultUserSetting
    if name == "DefaultToken":
        from .token import Token as DefaultToken

        return DefaultToken
    if name == "DefaultUserRole":
        from .role import UserRole as DefaultUserRole

        return DefaultUserRole
    if name == "BaseRoleEnum":
        from .base_roles import BaseRoleEnum as BaseRoleEnum

        return BaseRoleEnum

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
