"""Token model for API authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ...sqla import db
from ..base_perms_model import BasePermsModel
from ..model_mixins import UserOwnershipMixin

if TYPE_CHECKING:
    pass


class Token(UserOwnershipMixin, BasePermsModel):  # noqa: conflict-attribute
    """API tokens for user authentication.

    This model supports polymorphic inheritance, allowing applications to
    subclass Token with custom attributes while maintaining ORM relationships.

    Example:
        class CustomToken(Token):
            __mapper_args__ = {"polymorphic_identity": "custom_token"}
            custom_field: Mapped[str] = mapped_column(db.String(100))
    """

    __delegate_to_user__ = True
    __mapper_args__ = {
        "polymorphic_on": "discriminator",
        "polymorphic_identity": "token",
    }

    discriminator: Mapped[str] = mapped_column(
        db.String(50),
        default="token",
        nullable=False,
        server_default="token",
    )
    token: Mapped[str] = mapped_column(db.String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    expires_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
    revoked: Mapped[bool] = mapped_column(db.Boolean(), nullable=False, default=False)
    revoked_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
