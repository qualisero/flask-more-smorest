"""Type stubs for dynamically created classes in test_user_mixed_defaults.py"""

from typing import Any
import datetime as dt
from uuid import UUID
from sqlalchemy.orm import Mapped

class CustomUserRole:
    """Dynamically created UserRole - uses defaults from AbstractUserRole."""

    pass

class CustomDomain:
    """Dynamically created Domain - uses defaults from AbstractDomain."""

    pass

class CustomUser:
    """Dynamically created user class with custom nickname field."""

    # Only custom field - everything else inherited from AbstractUser
    nickname: str | None

class CustomToken:
    """Dynamically created Token with custom fields."""

    # Custom fields beyond AbstractToken
    description: str | None
    expires_at: dt.datetime | None
    revoked: bool
    revoked_at: dt.datetime | None

class CustomUserSetting:
    """Dynamically created UserSetting with custom scope field."""

    # Custom field beyond AbstractUserSetting
    scope: str
