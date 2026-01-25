"""UserSetting model for key-value storage."""

from __future__ import annotations

from ...sqla import db
from .abstract_setting import AbstractUserSetting


class UserSetting(AbstractUserSetting):
    """User-specific key-value settings storage.

    This is a concrete implementation of AbstractUserSetting. For customization,
    subclass AbstractUserSetting instead of this class.

    Permission checks are delegated to the owning user (inherited from AbstractUserSetting).

    Example:
        from sqlalchemy.orm import Mapped, mapped_column

        class CustomSetting(AbstractUserSetting):
            __tablename__ = "user_setting"
            metadata: Mapped[dict] = mapped_column(sa.JSON)
            __table_args__ = (db.UniqueConstraint("user_id", "key"),)
    """

    __table_args__ = (db.UniqueConstraint("user_id", "key"),)
