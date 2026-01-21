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


class Token(UserOwnershipMixin, BasePermsModel):
    """API tokens for user authentication."""

    __delegate_to_user__ = True

    token: Mapped[str] = mapped_column(db.String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    expires_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
    revoked: Mapped[bool] = mapped_column(db.Boolean(), nullable=False, default=False)
    revoked_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
