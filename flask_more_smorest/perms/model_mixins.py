"""Model mixins for extending User models with common functionality.

This module provides reusable mixins for adding common fields and
functionality to User models and other models in Flask-More-Smorest.
"""

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship, synonym

from flask_more_smorest.error.exceptions import ForbiddenError

if TYPE_CHECKING:
    from .user_models import User


class HasUserMixin:
    """Mixin to add user ID foreign key to a model.

    Adds a user_id field and user relationship to track which user
    owns or created the model instance.

    The mixin supports optional aliasing/nullable configuration via:
        - ``__user_field_name__``: custom attribute alias for ``user_id``
        - ``__user_relationship_name__``: custom alias for ``user``
        - ``__user_id_nullable__``: allow NULL owner IDs

    Example:
        >>> class Article(BasePermsModel, HasUserMixin):
        ...     __user_field_name__ = "author_id"
        ...     __user_relationship_name__ = "author"
        ...     __user_id_nullable__ = True
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        ...
        >>> article = Article(title="Test", author_id=current_user.id)
    """

    __user_field_name__ = "user_id"
    __user_relationship_name__ = "user"
    __user_id_nullable__ = False

    def __init_subclass__(cls, **kwargs: Any):
        """Configure user field and relationship aliases on subclass creation."""
        super().__init_subclass__(**kwargs)
        cls._configure_user_aliases()

    @classmethod
    def _user_column_nullable(cls) -> bool:
        return bool(getattr(cls, "__user_id_nullable__", False))

    @classmethod
    def _user_field_alias(cls) -> str:
        return str(getattr(cls, "__user_field_name__", "user_id"))

    @classmethod
    def _user_relationship_alias(cls) -> str:
        return str(getattr(cls, "__user_relationship_name__", "user"))

    @classmethod
    def _configure_user_aliases(cls) -> None:
        field_alias = cls._user_field_alias()
        rel_alias = cls._user_relationship_alias()

        if field_alias and field_alias != "user_id" and not hasattr(cls, field_alias):
            setattr(cls, field_alias, synonym("user_id"))
            cls._copy_annotation("user_id", field_alias)

        if rel_alias and rel_alias != "user" and not hasattr(cls, rel_alias):
            setattr(cls, rel_alias, synonym("user"))
            cls._copy_annotation("user", rel_alias)

    @classmethod
    def _copy_annotation(cls, source: str, target: str) -> None:
        annotations = dict(getattr(cls, "__annotations__", {}))
        source_type = annotations.get(source)
        if source_type is None:
            if source == "user_id":
                source_type = Mapped[uuid.UUID]
            else:
                source_type = Mapped["User"]
        annotations[target] = source_type
        setattr(cls, "__annotations__", annotations)

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID | None]:
        """User ID foreign key with optional nullability."""
        from .user_models import get_current_user_id

        nullable = cls._user_column_nullable()
        default_callable = None if nullable else get_current_user_id

        return mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=nullable,
            default=default_callable,
        )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        """Relationship to User model."""
        backref_name = f"{cls.__tablename__}s"  # type: ignore
        # Add backref to User model, unless it already exists
        from .user_models import User

        if hasattr(User, backref_name) or backref_name in ("user_roles", "user_settings", "tokens"):
            backref_arg = None
        else:
            backref_arg = backref(
                backref_name,
                cascade="all, delete-orphan",
                passive_deletes=True,
                lazy="dynamic",
            )

        return relationship("User", lazy="joined", foreign_keys=[getattr(cls, "user_id")], backref=backref_arg)


class UserCanReadWriteMixin(HasUserMixin):
    """Mixin to add user-based read/write permissions.

    Combines HasUserMixin with permission methods that allow users
    to read and write only their own records.

    Note:
        This mixin enforces __user_id_nullable__ = False to ensure
        automatic ownership assignment. Without an owner, the permission
        checks would always fail.

    Example:
        >>> class Note(BasePermsModel, UserCanReadWriteMixin):
        ...     content: Mapped[str] = mapped_column(sa.Text)
    """

    __user_id_nullable__ = False

    def _can_write(self) -> bool:
        """User can write if they are the owner of the object.

        Returns:
            True if current user owns this record
        """
        from .user_models import get_current_user_id

        return self.user_id == get_current_user_id()

    def _can_read(self) -> bool:
        """User can read if they are the owner of the object.

        Returns:
            True if current user owns this record
        """
        from .user_models import get_current_user_id

        return self.user_id == get_current_user_id()


class UserOwnedResourceMixin(HasUserMixin):
    """Mixin for resources owned by users with permission delegation.

    This mixin provides permission methods that delegate to the owning
    user's permission methods. Used for resources like tokens and settings
    that belong to a user and inherit the user's permissions.

    Requires:
        - A 'user' relationship to the User model

    Example:
        >>> class Token(BasePermsModel, UserOwnedResourceMixin):
        ...     user_id: Mapped[uuid.UUID] = mapped_column(...)
        ...     user: Mapped["User"] = relationship("User")
    """

    def _can_write(self) -> bool:
        """Resource can be modified by its owner.

        Returns:
            True if the owning user has write permission
        """
        return self.user._can_write()

    def _can_create(self) -> bool:
        """Resource can be created by its owner.

        Returns:
            True if the owning user has write permission
        """
        if self.user_id:
            from .user_models import User

            try:
                user = User.get_or_404(self.user_id)
            except ForbiddenError:
                return False

            return user._can_write()

        return self._can_write()

    def _can_read(self) -> bool:
        """Resource can be read by its owner.

        Returns:
            True if the owning user has write permission
        """
        return self._can_write()


# Commonly used mixins for extending User models
class TimestampMixin:
    """Mixin adding additional timestamp fields.

    Adds last_login_at and email_verified_at fields for tracking
    user authentication and verification events.

    Example:
        >>> class CustomUser(User, TimestampMixin):
        ...     pass
        >>> user.email_verified_at = dt.datetime.now()
    """

    last_login_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)


class ProfileMixin:
    """Mixin adding basic profile fields.

    Adds first_name, last_name, display_name, and avatar_url fields
    for user profile information.

    Example:
        >>> class CustomUser(User, ProfileMixin):
        ...     pass
        >>> print(user.full_name)
        'John Doe'
    """

    first_name: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    display_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    @property
    def full_name(self) -> str:
        """Get formatted full name.

        Returns:
            Full name as "first last", or just first or last if one is missing
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""


class SoftDeleteMixin:
    """Mixin adding soft delete functionality.

    Adds deleted_at timestamp and helper methods for soft deleting
    records (marking as deleted without removing from database).

    Example:
        >>> class CustomUser(User, SoftDeleteMixin):
        ...     pass
        >>> user.soft_delete()
        >>> print(user.is_deleted)
        True
    """

    deleted_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted.

        Returns:
            True if record has been soft deleted
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark record as soft deleted.

        Sets deleted_at to current time and optionally disables
        the record if is_enabled field exists.
        """
        self.deleted_at = dt.datetime.now(dt.timezone.utc)
        # Only set is_enabled if it exists
        if hasattr(self, "is_enabled"):
            self.is_enabled = False

    def restore(self) -> None:
        """Restore soft deleted record.

        Clears deleted_at and optionally re-enables the record
        if is_enabled field exists.
        """
        self.deleted_at = None
        # Only set is_enabled if it exists
        if hasattr(self, "is_enabled"):
            self.is_enabled = True
