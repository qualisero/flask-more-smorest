"""UserSetting model for key-value storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column

from ...sqla import db
from ..base_perms_model import BasePermsModel
from ..model_mixins import UserOwnershipMixin

if TYPE_CHECKING:
    pass


class UserSetting(UserOwnershipMixin, BasePermsModel):  # noqa: conflict-attribute
    """User-specific key-value settings storage."""

    __delegate_to_user__ = True

    key: Mapped[str] = mapped_column(db.String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "key"),)
