"""Abstract User model for Flask-More-Smorest authentication system.

Provides abstract base for User models with email/password auth, roles, settings, and tokens.
This is an abstract model - no table is created. Inherit from this to create concrete User models.
"""

from __future__ import annotations

import enum
import logging
import uuid
from typing import TYPE_CHECKING, Self, TypeVar

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...error.exceptions import UnprocessableEntity
from ...utils import check_password_hash, generate_password_hash
from ..base_perms_model import BasePermsModel
from ..user_context import AdminRole

if TYPE_CHECKING:
    from .abstract_role import AbstractUserRole
    from .abstract_setting import AbstractUserSetting
    from .abstract_token import AbstractToken

logger = logging.getLogger(__name__)


UserT = TypeVar("UserT", bound="AbstractUser")


class AbstractUser(BasePermsModel):
    """Abstract User model with email/password auth, roles, and domain support.

    This is an abstract base class - it does NOT create a database table.
    Subclasses must define concrete fields and table configuration.

    **Features (all inherited):**
    - Email/password authentication
    - Roles management via UserRole relationship
    - Settings management via UserSetting relationship
    - Token management via Token relationship
    - Permission checks (_can_read, _can_write, _can_create)
    - Admin properties (is_admin, is_superadmin)
    - Role checking (has_role, list_roles)

    **Subclassing example:**

    .. code-block:: python

        from flask_more_smorest.perms import AbstractUser, init_fms

        class CustomUser(AbstractUser):
            # Optional: custom fields only
            bio: Mapped[str | None] = mapped_column(sa.String(500))

            def _can_write(self, user) -> bool:
                return super()._can_write(user)

        # Register with the system
        init_fms(user=CustomUser)
    """

    __abstract__ = True  # No table is created
    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}  # noqa: RUF012

    email: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)
    password: Mapped[bytes | None] = mapped_column(sa.LargeBinary(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(
        sa.Boolean(),
        default=True,
        nullable=False,
        server_default=sa.true(),
    )

    @declared_attr
    def roles(cls) -> Mapped[list[AbstractUserRole]]:
        from ..user_registry import get_role_model

        return relationship(
            lambda: get_role_model(),
            back_populates="user",
            cascade="all, delete-orphan",
            enable_typechecks=False,
        )

    @declared_attr
    def settings(cls) -> Mapped[list[AbstractUserSetting]]:
        from ..user_registry import get_setting_model

        return relationship(
            lambda: get_setting_model(),
            back_populates="user",
            cascade="all, delete-orphan",
        )

    @declared_attr
    def tokens(cls) -> Mapped[list[AbstractToken]]:
        from ..user_registry import get_token_model

        return relationship(
            lambda: get_token_model(),
            back_populates="user",
            cascade="all, delete-orphan",
        )

    def __init__(self, **kwargs: object):
        """Create new user with optional password hashing."""
        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password:
            if not isinstance(password, str):
                raise TypeError("Password must be a string")
            self.set_password(password)

    @classmethod
    def get_current_user(cls: type[UserT]) -> UserT | None:
        """Get the current authenticated user of this User subclass.

        This provides zero-boilerplate typed access to the current user.
        Uses the application's configured authentication (JWT or custom getter).

        Returns:
            Current user instance of this User subclass if authenticated, None otherwise

        Example:
            >>> user = AbstractUser.get_current_user()
            >>> user = MyCustomUser.get_current_user()
        """
        from ..user_context import get_current_user

        # The overload in get_current_user handles the type narrowing
        return get_current_user(cls)

    def normalize_email(self, email: str | None) -> str | None:
        """Normalize email to lowercase for case-insensitive lookups.

        Emails are automatically converted to lowercase when set, ensuring:
        - Case-insensitive login (user@example.com == USER@EXAMPLE.COM)
        - Prevention of duplicate registrations with different cases
        - Efficient database queries using the email index
        - Consistent email storage throughout the application

        Args:
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
            >>> user.has_role("ADMIN")
            True
            >>> user.has_role("ADMIN", domain_name="main")
            True
        """
        # Normalize role to uppercase string for comparison
        # This handles both enum values and string inputs
        role_str = role.value.upper() if isinstance(role, enum.Enum) else str(role).upper()

        roles = self.roles
        return bool(
            any(
                r.role == role_str
                and (domain_name is None or r.domain is None or r.domain.name == domain_name or r.domain.name == "*")
                for r in roles
            )
        )

    def list_roles(self) -> list[str]:
        """List user roles as strings."""
        roles = self.roles
        return [r.role for r in roles]

    def _can_read(self, user: Self | None) -> bool:
        """Default read permission: users can read their own profile.

        Args:
            user: The current authenticated user, or None
        """

        if not user:
            return False
        try:
            return self.id == user.id or user.is_admin
        except Exception:
            return False

    def _can_write(self, user: Self | None) -> bool:
        """Default write permission: users can edit their own profile.

        Args:
            user: The current authenticated user, or None
        """

        if not user:
            return False
        try:
            if self.id == user.id:
                return True
            if self.is_admin:
                return user.is_superadmin
            return user.is_admin
        except Exception:
            return False

    def _can_create(self, user: Self | None) -> bool:
        """Default create permission: admins can create users, or public registration if enabled.

        Args:
            user: The current authenticated user, or None
        """

        # Check if public registration is enabled on the class
        if getattr(self.__class__, "PUBLIC_REGISTRATION", False):
            return True
        return user is not None and user.is_admin

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
