from typing import TYPE_CHECKING
import uuid
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship

# from iaoport_api.user import get_current_user_id, current_user

if TYPE_CHECKING:
    from .user import User, get_current_user_id, current_user


class HasUserMixin:
    """Mixin to add user ID to a model."""

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            default=get_current_user_id,
        )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship(
            "User",
            lazy="joined",
            foreign_keys=[getattr(cls, "user_id")],
        )


class UserCanReadWriteMixin(HasUserMixin):
    """Mixin to add user write permissions."""

    def _can_write(self):
        """User can write if they are the owner of the object."""
        return self.user_id == current_user.id

    def _can_read(self):
        """User can read if they are the owner of the object."""
        return self.user_id == current_user.id
