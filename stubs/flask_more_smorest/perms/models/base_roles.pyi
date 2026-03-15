"""Type stub for BaseRoleEnum."""

from enum import Enum

class BaseRoleEnum(str, Enum):  # type: ignore[misc]
    """Base role enumeration."""

    USER: str
    ADMIN: str
    SUPERADMIN: str
