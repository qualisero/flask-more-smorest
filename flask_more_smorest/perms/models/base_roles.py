import enum


class BaseRoleEnum(enum.StrEnum):
    """Default user role enumeration.

    Values are uppercase for backward compatibility with applications
    expecting uppercase role strings.
    """

    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    USER = "USER"
