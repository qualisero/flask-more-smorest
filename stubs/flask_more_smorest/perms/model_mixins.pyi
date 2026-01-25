"""Type stubs for model mixins."""

import datetime as dt
from typing import Any, TYPE_CHECKING
from uuid import UUID
from sqlalchemy.orm import Mapped

if TYPE_CHECKING:
    from .models.abstract_user import AbstractUser

class TimestampMixin:
    """Adds authentication-related timestamps: last_login_at, email_verified_at."""

    last_login_at: Mapped[dt.datetime | None]
    email_verified_at: Mapped[dt.datetime | None]

class ProfileMixin:
    """Adds profile fields: first_name, last_name, display_name, avatar_url.

    Property: ``full_name`` returns combined first/last name.
    """

    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    display_name: Mapped[str | None]
    avatar_url: Mapped[str | None]

    @property
    def full_name(self) -> str: ...
    @staticmethod
    def parse_full_name(full_name: str) -> dict[str, str]: ...
    @property
    def avatar(self) -> str | None: ...

class SoftDeleteMixin:
    """Soft delete with deleted_at timestamp and helper methods.

    Methods: ``soft_delete()`` marks as deleted, ``restore()`` clears.
    Property: ``is_deleted`` returns True if deleted_at is not None.
    """

    deleted_at: Mapped[dt.datetime | None]

    @property
    def is_deleted(self) -> bool: ...
    def soft_delete(self) -> None: ...
    def restore(self) -> None: ...
