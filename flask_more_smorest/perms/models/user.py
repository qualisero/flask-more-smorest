"""User model for Flask-More-Smorest authentication system.

Provides User model with email/password auth, roles, settings, and tokens.
"""

from __future__ import annotations

import enum
import logging
import uuid
from typing import TYPE_CHECKING, Any, TypeVar, cast

from flask_jwt_extended import current_user as jwt_current_user
from flask_jwt_extended import exceptions, verify_jwt_in_request
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ...error.exceptions import UnprocessableEntity
from ...sqla import db
from ...utils import check_password_hash, generate_password_hash
from ..base_perms_model import BasePermsModel
from ..user_context import AdminRole

if TYPE_CHECKING:
    from ..user_context import UserProtocol

logger = logging.getLogger(__name__)

UserType = TypeVar("UserType", bound="User")

# Set the current_user reference to JWT current user
current_user: UserProtocol = cast("UserProtocol", jwt_current_user)


def _get_jwt_current_user() -> UserProtocol | None:
    """JWT-based current user getter (private helper).

    Used as the default fallback when no custom function is registered.
    Applications should use get_current_user() from user_context instead.

    Returns:
        Current user instance if authenticated, None otherwise
    """
    try:
        verify_jwt_in_request()
    except exceptions.JWTExtendedException:
        return None
    except Exception as e:
        logger.exception("Error verifying JWT for current user: %s", e)
        return None

    # Resolve LocalProxy to get the actual user object
    try:
        resolved = current_user._get_current_object()  # type: ignore[attr-defined]
        return cast("UserProtocol | None", resolved)
    except (AttributeError, RuntimeError):
        return None


class User(BasePermsModel):
    """User model with email/password auth, roles, and domain support.

    Extend this class to add custom fields:

    .. code-block:: python

        class CustomUser(User):
            bio: Mapped[str | None] = mapped_column(db.String(500))
            age: Mapped[int | None] = mapped_column(db.Integer)

            def _can_write(self, current_user) -> bool:
                if self.age and self.age < 18:
                    return False  # Minors can't edit
                return super()._can_write(current_user)

            @property
            def is_adult(self) -> bool:
                return self.age is not None and self.age >= 18

    **Built-in features:**
    - `roles`: UserRole relationship
    - `settings`: UserSetting relationship
    - `tokens`: Token relationship
    - `is_admin`/`is_superadmin`: Properties
    - `has_role()`: Check role membership

    **Public registration:**
    Set `PUBLIC_REGISTRATION = True` on subclass to allow signups.
    """

    __tablename__ = "user"
    __mapper_args__ = {
        "polymorphic_on": "discriminator",
        "polymorphic_identity": "user",
    }  # Enable polymorphic inheritance
    __table_args__ = {"extend_existing": True}  # Allow subclasses to extend the table
    PUBLIC_REGISTRATION: bool = False  # Allow subclasses to enable public registration

    # Discriminator column for polymorphic inheritance
    discriminator: Mapped[str] = mapped_column(
        db.String(50),
        default="user",
        nullable=False,
        server_default="user",
        index=True,
    )

    # Core authentication fields that all User models must have
    email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
    password: Mapped[bytes | None] = mapped_column(db.LargeBinary(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Process User subclasses and inject __table_args__ for single-table inheritance.

        This method sets a marker (_User__is_single_table_inheritance) to communicate
        with __table_cls__() whether extend_existing=True should be injected during
        table creation.

        The marker is set BEFORE super().__init_subclass__() so it's available when
        SQLAlchemy calls __table_cls__() during class initialization. This allows
        injecting extend_existing at the right moment without SQLAlchemy rejecting it.

        Users do NOT need to manually add __table_args__ in their subclasses.
        """
        # Check for multi-table inheritance BEFORE SQLAlchemy processes the class
        has_custom_tablename = "__tablename__" in cls.__dict__
        has_custom_table_args = "__table_args__" in cls.__dict__

        # Set polymorphic identity for subclasses (if not already set)
        if cls is not User:
            # Check if __mapper_args__ is already defined on this class (not inherited)
            has_custom_mapper_args = "__mapper_args__" in cls.__dict__
            if not has_custom_mapper_args:
                # Check if it's in the class's direct __dict__ (might have been set previously)
                class_mapper_args = cls.__dict__.get("__mapper_args__", None)
                if (
                    class_mapper_args is None
                    or not isinstance(class_mapper_args, dict)
                    or "polymorphic_identity" not in class_mapper_args
                ):
                    # Use class name as polymorphic identity
                    cls.__mapper_args__ = {"polymorphic_identity": cls.__name__.lower()}

        # Set marker for __table_cls__() if using single-table inheritance
        # NOTE: We check ONLY for custom __tablename__ and __table_args__, not __mapper_args__
        # This ensures extend_existing=True is injected even when subclasses define __mapper_args__
        # (e.g., to set polymorphic_identity), which is the common STI pattern.
        if not has_custom_tablename and not has_custom_table_args:
            cls._User__is_single_table_inheritance = True

        super().__init_subclass__(**kwargs)

    @classmethod
    def __table_cls__(cls, *args: object, **kwargs: object) -> Any:
        """Override table creation to inject extend_existing for single-table inheritance.

        This is called by SQLAlchemy during __init_subclass__() to create the Table object.
        We inject extend_existing=True here if the marker was set, which happens at the
        perfect moment to avoid SQLAlchemy's "Can't place __table_args__" error.
        """
        # Check if marker was set by __init_subclass__
        if getattr(cls, "_User__is_single_table_inheritance", False):
            # Inject extend_existing into kwargs
            if "extend_existing" not in kwargs:
                kwargs["extend_existing"] = True

        return cast(Any, super()).__table_cls__(*args, **kwargs)

    # Core relationships that all User models inherit
    # Using enable_typechecks=False to allow UserRole subclasses
    @declared_attr
    def roles(cls) -> Mapped[list[UserRole]]:  # type: ignore[name-defined]  # noqa: F821
        """Relationship to user roles - inherited by all User models."""
        return relationship(
            "UserRole",
            back_populates="user",
            cascade="all, delete-orphan",
            enable_typechecks=False,  # Allow UserRole subclasses
        )

    @declared_attr
    def settings(cls) -> Mapped[list[UserSetting]]:  # type: ignore[name-defined]  # noqa: F821
        """Relationship to user settings - inherited by all User models."""
        return relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")

    @declared_attr
    def tokens(cls) -> Mapped[list[Token]]:  # type: ignore[name-defined]  # noqa: F821
        """Relationship to user tokens - inherited by all User models."""
        return relationship("Token", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs: object):
        """Create new user with optional password hashing."""
        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password:
            if not isinstance(password, str):
                raise TypeError("Password must be a string")
            self.set_password(password)

    @classmethod
    def get_current_user(cls: type[UserType]) -> UserType | None:
        """Get the current authenticated user of this User subclass.

        This provides zero-boilerplate typed access to the current user.
        Uses the application's configured authentication (JWT or custom getter).

        Returns:
            Current user instance of this User subclass if authenticated, None otherwise

        Example:
            >>> user = User.get_current_user()
            >>> user = MyUser.get_current_user()
        """
        from ..user_context import get_current_user

        return cast("UserType | None", get_current_user(cls))

    @validates("email")
    def normalize_email(self, key: str, email: str | None) -> str | None:
        """Normalize email to lowercase for case-insensitive lookups.

        Emails are automatically converted to lowercase when set, ensuring:
        - Case-insensitive login (user@example.com == USER@EXAMPLE.COM)
        - Prevention of duplicate registrations with different cases
        - Efficient database queries using the email index
        - Consistent email storage throughout the application

        Args:
            key: Field name (always "email")
            email: Email address to normalize

        Returns:
            Lowercase email address, or None if email is None
        """
        return email.lower() if email else email

    def set_password(self, password: str) -> None:
        """Set password with secure hashing."""
        self.password = generate_password_hash(password)

    def is_password_correct(self, password: str) -> bool:
        """Check if provided password matches stored hash."""
        if self.password is None:
            return False
        return isinstance(password, str) and check_password_hash(password=password, hashed=self.password)

    def update(self, commit: bool = True, **kwargs: str | int | float | bool | bytes | None) -> None:
        """Update user with password handling."""
        password = kwargs.pop("password", None)
        old_password = kwargs.pop("old_password", None)

        if password and not getattr(self, "perms_disabled", False):
            if old_password is None:
                raise UnprocessableEntity(
                    fields={"old_password": "Cannot be empty"},
                    message="Must provide old_password to set new password",
                )
            if not self.is_password_correct(str(old_password)):
                raise UnprocessableEntity(
                    message="Old password is incorrect",
                    fields={"old_password": "Old password is incorrect"},
                    location="json",
                )

        super().update(commit=False, **kwargs)
        if password:
            self.set_password(str(password))
        self.save(commit=commit)

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        return self.has_role(ROLE_ADMIN) or self.has_role(ROLE_SUPERADMIN)

    @property
    def is_superadmin(self) -> bool:
        """Check if user has superadmin privileges."""
        from ..user_context import ROLE_SUPERADMIN

        return self.has_role(ROLE_SUPERADMIN)

    def has_role(self, role: AdminRole | str | enum.Enum, domain_name: str | None = None) -> bool:
        """Check if user has specified role, optionally scoped to domain.

        Args:
            role: Role to check (string or enum value)
            domain_name: Optional domain name to scope the check

        Returns:
            True if user has the role, False otherwise

        Example:
            >>> user.has_role(DefaultUserRole.ADMIN)
            True
            >>> user.has_role("admin", domain_name="main")
            True
        """
        # Normalize role to string for comparison
        role_str = role.value if isinstance(role, enum.Enum) else str(role)

        roles = cast(list["UserRole"], self.roles)  # type: ignore[name-defined, redundant-cast]  # noqa: F821
        return bool(
            any(
                r.role == role_str
                and (domain_name is None or r.domain is None or r.domain.name == domain_name or r.domain.name == "*")
                for r in roles
            )
        )

    def list_roles(self) -> list[str]:
        """List user roles as strings."""
        roles = cast(list["UserRole"], self.roles)  # type: ignore[name-defined, redundant-cast]  # noqa: F821
        return [r.role for r in roles]

    def _can_read(self, current_user: Any) -> bool:
        """Default read permission: users can read their own profile.

        Args:
            current_user: The current authenticated user, or None
        """
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        if self._should_bypass_perms():
            return True

        user = current_user
        if not user:
            return False
        try:
            return cast(bool, self.id == user.id or user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))
        except Exception:
            return False

    def _can_write(self, current_user: Any) -> bool:
        """Default write permission: users can edit their own profile.

        Args:
            current_user: The current authenticated user, or None
        """
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        if self._should_bypass_perms():
            return True

        user = current_user
        if not user:
            return False
        try:
            if self.id == user.id:
                return True
            if self.is_admin:
                return cast(bool, user.has_role(ROLE_SUPERADMIN))
            return cast(bool, user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))
        except Exception:
            return False

    def _can_create(self, current_user: Any) -> bool:
        """Default create permission: admins can create users, or public registration if enabled.

        Args:
            current_user: The current authenticated user, or None
        """
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        # Check if public registration is enabled on the class
        if getattr(self.__class__, "PUBLIC_REGISTRATION", False):
            return True
        user = current_user
        if user is None:
            return True
        return cast(bool, user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))

    # Concrete methods that use relationships - available to all User models
    @property
    def num_tokens(self) -> int:
        """Get number of tokens for this user."""
        return len(self.tokens)

    @property
    def domain_ids(self) -> set[uuid.UUID | str]:
        """Return set of domain IDs the user has roles for."""
        return {r.domain_id or "*" for r in self.roles}

    def has_domain_access(self, domain_id: uuid.UUID | None) -> bool:
        """Check if user has access to a specific domain.

        Users have access to a domain if they have any role associated with that domain,
        or if they have a wildcard role (*). Superadmins automatically have access.

        Args:
            domain_id: Domain UUID to check access for, or None for global access

        Returns:
            True if user has access to the domain, False otherwise

        Example:
            >>> user.has_domain_access(domain_id)
            True
            >>> user.has_domain_access(None)  # Global access check
            True
        """
        return domain_id is None or domain_id in self.domain_ids or "*" in self.domain_ids
