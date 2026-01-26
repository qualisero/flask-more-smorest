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
    from flask_more_smorest.perms.models.defaults import User

    # Register the defaults
    init_fms(user=User)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_roles import BaseRoleEnum
    from .role import Domain, UserRole
    from .setting import UserSetting
    from .token import Token
    from .user import User

__all__ = [
    "BaseRoleEnum",
    "Domain",
    "Token",
    "User",
    "UserRole",
    "UserSetting",
]


def __getattr__(name: str) -> object:
    if name == "User":
        from .user import User

        return User
    if name == "Domain":
        from .role import Domain

        return Domain
    if name == "UserSetting":
        from .setting import UserSetting

        return UserSetting
    if name == "Token":
        from .token import Token

        return Token
    if name == "UserRole":
        from .role import UserRole

        return UserRole
    if name == "BaseRoleEnum":
        from .base_roles import BaseRoleEnum

        return BaseRoleEnum

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
