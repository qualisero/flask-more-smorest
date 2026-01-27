"""User-related models for Flask-More-Smorest.

This module exports abstract user-related models. Concrete default
implementations live in ``flask_more_smorest.perms.models.defaults`` and
are only loaded when explicitly imported.

Version: 0.10.1
"""

from __future__ import annotations

from .abstract_role import AbstractDomain, AbstractUserRole
from .abstract_setting import AbstractUserSetting
from .abstract_token import AbstractToken
from .abstract_user import AbstractUser

__all__ = [
    "AbstractDomain",
    "AbstractToken",
    "AbstractUser",
    "AbstractUserRole",
    "AbstractUserSetting",
]
