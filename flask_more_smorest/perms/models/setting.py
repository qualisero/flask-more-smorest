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
    """User-specific key-value settings storage.

    This model supports polymorphic inheritance, allowing applications to
    subclass UserSetting with custom attributes while maintaining ORM relationships.

    Example:
        class CustomSetting(UserSetting):
            __mapper_args__ = {"polymorphic_identity": "custom_setting"}
            metadata: Mapped[dict] = mapped_column(db.JSON)
    """

    __delegate_to_user__ = True
    __mapper_args__ = {
        "polymorphic_on": "discriminator",
        "polymorphic_identity": "user_setting",
    }

    discriminator: Mapped[str] = mapped_column(
        db.String(50),
        default="user_setting",
        nullable=False,
        server_default="user_setting",
    )
    key: Mapped[str] = mapped_column(db.String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "key"),)
