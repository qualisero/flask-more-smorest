"""Reusable mixins for User models and other models in Flask-More-Smorest."""

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship, synonym

if TYPE_CHECKING:
    from .models.user import User


class HasUserMixin:
    """Adds user_id foreign key and user relationship to a model.

    Configuration:
        - ``__user_field_name__``: Custom alias for user_id (default: "user_id")
        - ``__user_relationship_name__``: Custom alias for user (default: "user")
        - ``__user_id_nullable__``: Allow NULL owner IDs (default: False)
        - ``__user_backref_name__``: Custom backref on User model
            - ``None`` (default): Auto-generate as ``{tablename}s`` (e.g., "articles")
            - Custom string: Use specified name
            - ``""``: Skip backref creation

    Example:
        >>> class Article(BasePermsModel, HasUserMixin):
        ...     __user_backref_name__ = "written_articles"
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        >>> user.written_articles  # Custom backref
    """

    __user_field_name__ = "user_id"
    __user_relationship_name__ = "user"
    __user_id_nullable__ = False
    __user_backref_name__: str | None = None  # None means auto-generate

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
    def _user_backref_name(cls) -> str | None:
        """Get backref name: custom if set, or auto-generated from tablename, or None to skip."""
        custom_name: str | None = getattr(cls, "__user_backref_name__", None)
        if custom_name is not None:
            return custom_name
        return f"{cls.__tablename__}s"  # type: ignore

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
            source_type = Mapped[uuid.UUID] if source == "user_id" else Mapped["User"]
        annotations[target] = source_type
        cls.__annotations__ = annotations

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID | None]:
        """User ID foreign key with optional nullability."""
        from .user_context import get_current_user_id

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
        """Relationship to the registered User model.

        Uses lazy resolution via lambda to support custom User models registered
        through init_fms(). The lambda is evaluated during mapper configuration,
        allowing get_user_model() to return the correct registered User class.
        """
        from .user_registry import get_user_model

        backref_name = cls._user_backref_name()

        # Build backref if needed
        # Standard User relationships: "roles" (from user_roles), "settings" (from user_settings), "tokens"
        if backref_name and backref_name not in ("roles", "settings", "tokens"):
            backref_arg = backref(
                backref_name,
                cascade="all, delete-orphan",
                passive_deletes=True,
                lazy="dynamic",
            )
        else:
            backref_arg = None

        # Use lambda to get registered User model dynamically
        # The lambda is called during mapper configuration, not at class definition time
        return relationship(
            lambda: get_user_model(),
            lazy="joined",
            foreign_keys=[cls.user_id],  # type: ignore[list-item]
            backref=backref_arg,
        )


class UserOwnershipMixin(HasUserMixin):
    """User-owned resources with configurable permission delegation.

    Two modes:

    1. **Simple Ownership** (default, ``__delegate_to_user__ = False``):
       - Compares ``user_id == current_user.id``
       - Use for: Notes, posts, comments

    2. **Delegated Permissions** (``__delegate_to_user__ = True``):
       - Calls ``self.user._can_write(current_user)``
       - Use for: Tokens, settings, API keys

    Attributes:
        __delegate_to_user__: Delegate to user's permission methods (default: False)
        __user_id_nullable__: Allow NULL owner IDs (default: False)

    Example:
        >>> class Token(UserOwnershipMixin, BasePermsModel):
        ...     __delegate_to_user__ = True
        ...     token: Mapped[str] = mapped_column(sa.String(500))
        >>> # Delegates to user's permission methods
    """

    __user_id_nullable__ = False
    __delegate_to_user__ = False

    def _can_write(self, user: Any) -> bool:
        if self.__delegate_to_user__:
            return self.user._can_write(user)
        return bool(user) and self.user_id == user.id

    def _can_read(self, user: Any) -> bool:
        if self.__delegate_to_user__:
            return self._can_write(user)
        return bool(user) and self.user_id == user.id

    def _can_create(self, user: Any) -> bool:
        if not self.__delegate_to_user__:
            return True

        if self.user_id:
            from ..sqla import db
            from .user_registry import get_user_model

            UserModel = get_user_model()

            # Use db.session.get() instead of get_or_404() to avoid permission check
            # during delegation. We don't need to verify read permission on the owner
            # user - we only need to delegate the write permission check.
            owner = db.session.get(UserModel, self.user_id)
            if not owner:
                return False

            return owner._can_write(user)

        return self._can_write(user)


# Commonly used mixins for extending User models
class TimestampMixin:
    """Adds authentication-related timestamps: last_login_at, email_verified_at."""

    last_login_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)


class ProfileMixin:
    """Adds profile fields: first_name, last_name, display_name, avatar_url.

    Property: ``full_name`` returns combined first/last name.
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

    @classmethod
    def parse_full_name(cls, full_name: str) -> dict[str, str]:
        """Parse a full name into first and last name components.

        Strips leading/trailing whitespace and splits on first space.
        Everything after the first space is considered the last name.

        Args:
            full_name: The full name string

        Returns:
            Dictionary with 'first_name' and 'last_name' keys
        """
        # Strip and split on any whitespace
        parts = full_name.strip().split(None, 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        return {"first_name": first_name, "last_name": last_name}

    @property
    def avatar(self) -> str | None:
        """Get avatar URL (alias for avatar_url).

        Override this property to implement custom avatar logic
        (e.g., generating Gravatar or Initials avatar if avatar_url is missing).
        """
        return self.avatar_url


class SoftDeleteMixin:
    """Soft delete with deleted_at timestamp and helper methods.

    Methods: ``soft_delete()`` marks as deleted, ``restore()`` clears.
    Property: ``is_deleted`` returns True if deleted_at is not None.
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
        self.deleted_at = dt.datetime.now(dt.UTC)
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
