"""Abstract UserSetting model for key-value storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..base_perms_model import BasePermsModel
from ..model_mixins import UserOwnershipMixin

if TYPE_CHECKING:
    pass


class AbstractUserSetting(UserOwnershipMixin, BasePermsModel):
    """Abstract UserSetting model for key-value storage.

    This is an abstract base class - it does NOT create a database table.
    Subclasses must define concrete fields and table configuration.

    Permission checks are delegated to the owning user by default
    (via UserOwnershipMixin). Override _can_read/_can_write/_can_create
    to customize.

    **Subclassing example:**

    .. code-block:: python

        from flask_more_smorest.perms import AbstractUserSetting

        class CustomUserSetting(AbstractUserSetting):
            __tablename__ = "user_setting"

            key: Mapped[str] = mapped_column(db.String(80), nullable=False)
            value: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)

            __table_args__ = (db.UniqueConstraint("user_id", "key"),)

            # Optional: custom fields
            metadata: Mapped[dict] = mapped_column(db.JSON, default={})
            encrypted: Mapped[bool] = mapped_column(db.Boolean, default=False)
    """

    __abstract__ = True  # No table is created
    __tablename__ = "user_setting"
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]] = {"extend_existing": True}
    __delegate_to_user__ = True  # Delegate permission checks to user
    __user_backref_name__ = "settings"  # Backref on User model

    key: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
