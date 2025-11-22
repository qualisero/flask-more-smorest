"""
User models and authentication system for Flask-More-Smorest.

This module provides:
1. User - Default user model with role-based permissions
2. UserRole/UserSetting - Related models for user management
3. Token-based authentication integration
4. Mixins for common user model extensions

The system supports:
- Custom user models through simple inheritance
- Role-based permissions with domain scoping
- Multi-tenant applications
- JWT token authentication
- Flexible user data storage

Example usage:
    # Use default User model
    from flask_more_smorest import User

    # Or extend with custom fields
    class CustomUser(User):
        bio: Mapped[str] = mapped_column(db.String(500))

        # Override methods if needed
        def _can_write(self) -> bool:
            return self.is_verified and super()._can_write()
"""

import logging
import uuid
import enum
import os
import datetime as dt
from typing import TYPE_CHECKING, Any, Type
from abc import ABC, abstractmethod

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.declarative import declared_attr

from .database import db
from .utils import check_password_hash, generate_password_hash
from .exceptions import UnprocessableEntity
from .models import BaseModel

from flask_jwt_extended import verify_jwt_in_request, current_user as jwt_current_user, exceptions

logger = logging.getLogger(__name__)


class User(BaseModel):
    """User model with role-based permissions and domain support.

    This is the main User model for Flask-More-Smorest applications.
    Projects can use this as-is or extend it with additional fields and methods.

    To create a custom user model, simply inherit from this class:

        class CustomUser(User):
            bio: Mapped[str] = mapped_column(db.String(500))
            age: Mapped[int] = mapped_column(db.Integer)

            # Override methods if needed
            def _can_write(self) -> bool:
                return self.age >= 18 and super()._can_write()

    The User model provides:
    - Email-based authentication with password hashing
    - Role-based permissions with domain scoping
    - JWT token support for API authentication
    - Relationships to roles, settings, and tokens
    - Permission checking methods (_can_read, _can_write, etc.)
    """

    __tablename__ = "users"

    # Core authentication fields that all User models must have
    email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
    password: Mapped[bytes | None] = mapped_column(db.LargeBinary(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)

    # Core relationships that all User models inherit
    # Using declared_attr for proper inheritance in custom User models
    @declared_attr
    def roles(cls) -> Mapped[list["UserRole"]]:
        """Relationship to user roles - inherited by all User models."""
        return relationship("UserRole", back_populates="user", cascade="all, delete-orphan")

    @declared_attr
    def settings(cls) -> Mapped[list["UserSetting"]]:
        """Relationship to user settings - inherited by all User models."""
        return relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")

    @declared_attr
    def tokens(cls) -> Mapped[list["Token"]]:
        """Relationship to user tokens - inherited by all User models."""
        return relationship("Token", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Create new user with optional password hashing."""
        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password:
            self.set_password(password)

    def set_password(self, password: str) -> None:
        """Set password with secure hashing."""
        self.password = generate_password_hash(password)

    def is_password_correct(self, password: str) -> bool:
        """Check if provided password matches stored hash."""
        if self.password is None:
            return False
        return isinstance(password, str) and check_password_hash(password=password, hashed=self.password)

    def update(self, commit: bool = True, force: bool = False, **kwargs) -> "User":
        """Update user with password handling."""
        password = kwargs.pop("password", None)
        old_password = kwargs.pop("old_password", None)

        if password and not getattr(self, "perms_disabled", False):
            if old_password is None:
                raise UnprocessableEntity(
                    fields={"old_password": "Cannot be empty"},
                    message="Must provide old_password to set new password",
                )
            if not self.is_password_correct(old_password):
                raise UnprocessableEntity(
                    message="Old password is incorrect",
                    fields={"old_password": "Old password is incorrect"},
                    location="json",
                )

        super().update(commit=False, **kwargs)
        if password:
            self.set_password(password)
        return self.save(commit=commit)

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.has_role(UserRole.Role.ADMIN) or self.is_superadmin

    @property
    def is_superadmin(self) -> bool:
        """Check if user has superadmin privileges."""
        return self.has_role(UserRole.Role.SUPERADMIN)

    def has_role(self, role: "UserRole.Role", domain_name: str | None = None) -> bool:
        """Check if user has specified role, optionally scoped to domain."""
        return any(
            r.role == role
            and (domain_name is None or r.domain is None or r.domain.name == domain_name or r.domain.name == "*")
            for r in self.roles
        )

    def _can_write(self) -> bool:
        """Default write permission: users can edit their own profile."""
        try:
            return self.id == get_current_user().id
        except Exception:
            return False

    def _can_create(self) -> bool:
        """Default create permission: admins can create users."""
        try:
            return get_current_user().is_admin
        except Exception:
            return True  # Allow during testing/setup

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
        """Check if user has access to specified domain."""
        return domain_id is None or domain_id in self.domain_ids or "*" in self.domain_ids


# Storage for the configured User model
def get_current_user() -> "User":
    """Get the current user from flask_jwt_extended."""
    return jwt_current_user


def get_current_user_id() -> uuid.UUID | None:
    """Get current user ID."""
    try:
        verify_jwt_in_request()
        return get_current_user().id
    except exceptions.JWTDecodeError:
        return None
    except Exception as e:
        logger.exception("Error getting current user ID: %s", e)
        return None


# Set the current_user reference to JWT current user
current_user = jwt_current_user


class Domain(BaseModel):
    """Distinct domains within the app for multi-tenant support."""

    __tablename__ = "domains"

    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)

    @classmethod
    def get_default_domain_id(cls) -> uuid.UUID | None:
        """Get the default domain ID from environment or first available."""
        if default_domain := os.getenv("DEFAULT_DOMAIN_NAME"):
            if domain := cls.query.filter_by(name=default_domain).first():
                return domain.id
        if domain := cls.query.first():
            return domain.id
        return None

    def _can_read(self) -> bool:
        """Any user can read domains."""
        return True


class UserRole(BaseModel):
    """User roles with domain scoping for multi-tenant applications."""

    __tablename__ = "user_roles"

    class Role(str, enum.Enum):
        """Predefined user roles."""

        SUPERADMIN = "superadmin"
        ADMIN = "admin"
        EDITOR = "editor"
        USER = "user"

    # Use string reference for User to support custom models
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        db.ForeignKey("domains.id"),
        nullable=True,
        default=None,
    )

    # Relationships
    domain: Mapped["Domain | None"] = relationship("Domain")
    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped[Role] = mapped_column(sa.types.Enum(Role, native_enum=False), nullable=False)

    def __init__(self, domain_id: uuid.UUID | str | None = None, **kwargs):
        """Initialize role with domain handling."""
        if domain_id is None:
            domain_id = Domain.get_default_domain_id()
        # Force explicit use of '*' to set domain_id to None:
        if domain_id == "*":
            domain_id = None
        super().__init__(domain_id=domain_id, **kwargs)

    def _can_write(self) -> bool:
        """Permission check for modifying roles."""
        try:
            current = get_current_user()
            if self.role in (self.Role.SUPERADMIN, self.Role.ADMIN):
                return current.is_superadmin
            return current.is_admin
        except Exception:
            return True  # Allow for testing

    def _can_create(self) -> bool:
        """Permission check for creating roles."""
        return self._can_write()

    def _can_read(self) -> bool:
        """Permission check for reading roles."""
        try:
            return self.user._can_read()
        except Exception:
            return True


class Token(BaseModel):
    """API tokens for user authentication."""

    __tablename__ = "tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="tokens")
    token: Mapped[str] = mapped_column(db.String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    expires_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
    revoked: Mapped[bool] = mapped_column(db.Boolean(), nullable=False, default=False)
    revoked_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)

    def _can_write(self) -> bool:
        """Tokens can be modified by their owner."""
        try:
            return self.user._can_write()
        except Exception:
            return True

    def _can_create(self) -> bool:
        """Tokens can be created by their owner."""
        return self._can_write()

    def _can_read(self) -> bool:
        """Tokens can be read by their owner."""
        return self._can_write()


class UserSetting(BaseModel):
    """User-specific key-value settings storage."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="settings")
    key: Mapped[str] = mapped_column(db.String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "key"),)

    def _can_write(self) -> bool:
        """Settings can be modified by their owner."""
        try:
            return self.user._can_write()
        except Exception:
            return True

    def _can_create(self) -> bool:
        """Settings can be created by their owner."""
        return self._can_write()

    def _can_read(self) -> bool:
        """Settings can be read by their owner."""
        return self._can_write()


# Commonly used mixins for extending User models
class TimestampMixin:
    """Mixin adding additional timestamp fields."""

    last_login_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)
    email_verified_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(), nullable=True)


class ProfileMixin:
    """Mixin adding basic profile fields."""

    first_name: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    last_name: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    display_name: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    @property
    def full_name(self) -> str:
        """Get formatted full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or ""


class SoftDeleteMixin:
    """Mixin adding soft delete functionality."""

    deleted_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark record as soft deleted."""
        from datetime import datetime, timezone

        self.deleted_at = datetime.now(timezone.utc)
        self.is_enabled = False

    def restore(self) -> None:
        """Restore soft deleted record."""
        self.deleted_at = None
        self.is_enabled = True
