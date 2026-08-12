"""Type stub for BaseRoleEnum."""

import enum

class BaseRoleEnum(enum.StrEnum):
    """Base role enumeration."""

    USER = "USER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
