"""Type stub for BaseRoleEnum."""

from enum import StrEnum

class BaseRoleEnum(StrEnum):
    """Base role enumeration."""

    USER = "USER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
