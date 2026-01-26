"""Abstract Token model for API authentication."""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..base_perms_model import BasePermsModel
from ..model_mixins import UserOwnershipMixin


class AbstractToken(UserOwnershipMixin, BasePermsModel):
    """Abstract Token model for API authentication.

    This is an abstract base class - it does NOT create a database table.
    Subclasses must define concrete fields and table configuration.

    Permission checks are delegated to the owning user by default
    (via UserOwnershipMixin). Override _can_read/_can_write/_can_create
    to customize.

    **Subclassing example:**

    .. code-block:: python

        from flask_more_smorest.perms import AbstractToken

        class CustomToken(AbstractToken):
            __tablename__ = "token"

            token: Mapped[str] = mapped_column(db.String(1024), nullable=False)
            description: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
            expires_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
            revoked: Mapped[bool] = mapped_column(db.Boolean(), nullable=False, default=False)
            revoked_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)

            # Optional: custom fields
            last_used_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
            ip_address: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    """

    __abstract__ = True  # No table is created
    __tablename__ = "token"
    __table_args__ = {"extend_existing": True}  # noqa: RUF012
    __delegate_to_user__ = True  # Delegate permission checks to user
    __user_backref_name__ = "tokens"  # Backref on User model

    token: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)
    revoked: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)
