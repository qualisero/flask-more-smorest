"""User model for Flask-More-Smorest authentication system.

Provides User model with email/password auth, roles, settings, and tokens.
"""

from __future__ import annotations

import enum
import logging
import uuid
from typing import Self, TypeVar, cast

from flask_jwt_extended import current_user as jwt_current_user
from flask_jwt_extended import exceptions, verify_jwt_in_request

from ...error.exceptions import UnprocessableEntity
from ...utils import check_password_hash, generate_password_hash
from ..user_context import AdminRole
from .abstract_user import AbstractUser

logger = logging.getLogger(__name__)

UserModelT = TypeVar("UserModelT", bound="User")

# TODO: should probably not have this top-level proxy here and only use get_current_user()
# current_user: LocalProxy[AbstractUser] = cast("LocalProxy[AbstractUser]", jwt_current_user)


def _get_jwt_current_user() -> AbstractUser | None:
    """Get current authenticated user via JWT.

    This is used as the default fallback when no custom function is registered.
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
        resolved = jwt_current_user._get_current_object()
        return cast("AbstractUser | None", resolved)
    except (AttributeError, RuntimeError):
        return None


class User(AbstractUser):
    """User model with email/password auth, roles, and domain support.

    This is a concrete implementation of AbstractUser. For customization,
    subclass AbstractUser instead of this class.

    Example:

    .. code-block:: python

        from flask_more_smorest.perms.models import AbstractUser

        class CustomUser(AbstractUser):
            __tablename__ = "user"

            bio: Mapped[str | None] = mapped_column(db.String(500))
            age: Mapped[int | None] = mapped_column(db.Integer)

            def _can_write(self, user) -> bool:
                if self.age and self.age < 18:
                    return False  # Minors can't edit
                return super()._can_write(user)

            @property
            def is_adult(self) -> bool:
                return self.age is not None and self.age >= 18
    """

    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}  # noqa: RUF012
    PUBLIC_REGISTRATION: bool = False

    def __init__(self, **kwargs: object):
        """Create new user with optional password hashing."""
        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password:
            if not isinstance(password, str):
                raise TypeError("Password must be a string")
            self.set_password(password)

    @classmethod
    def get_current_user(cls: type[UserModelT]) -> UserModelT | None:
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

        return cast("UserModelT | None", get_current_user(cls))

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
        return email.lower() if email else None

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
        # This handles both enum values (already uppercase) and string inputs
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
            return self.id == user.id
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


# Import uuid for type annotations
