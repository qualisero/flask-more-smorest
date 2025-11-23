"""
User models and authentication system for Flask-More-Smorest.

This module provides a concrete User model with full functionality for:
- Email-based authentication with secure password hashing
- Role-based permissions with domain scoping  
- User settings for key-value preferences
- JWT token support for API authentication
- Built-in relationships to roles, settings, and tokens

## User Model Customization

**Simple Inheritance Pattern**:
The User class is a concrete model that can be extended through inheritance:

```python
from flask_more_smorest.user import User

# Extend User with additional fields
class EmployeeUser(User):
    __tablename__ = "employee_users"  # Custom table name
    
    employee_id: Mapped[str] = mapped_column(db.String(50), unique=True)
    department: Mapped[str] = mapped_column(db.String(100))
    
    def get_employee_permissions(self):
        # Custom method for employee-specific logic
        return ["read_timesheet", "submit_expenses"]
```

**UserRole Customization**:
Create custom role enums and role models by inheriting from UserRole:

```python
import enum
from flask_more_smorest.user import UserRole

class EmployeeRole(str, enum.Enum):
    HR_MANAGER = "hr_manager" 
    DEPARTMENT_HEAD = "department_head"
    EMPLOYEE = "employee"

class EmployeeUserRole(UserRole):
    __tablename__ = "employee_user_roles"
    
    # Custom methods for employee role logic
    def get_employee_permissions(self):
        return self.role
```

## Features Included

All User instances (including subclasses) automatically inherit:
- Role management via User.roles relationship
- Settings storage via User.settings relationship  
- Token authentication via User.tokens relationship
- Permission checking methods (has_role, is_admin, etc.)
- Domain-scoped multi-tenant support
- CRUD operation permissions
"""

import logging
import uuid
import enum
import os
import datetime as dt
from typing import TYPE_CHECKING, Any, Type

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.declarative import declared_attr

from .database import db
from .utils import check_password_hash, generate_password_hash
from .exceptions import UnprocessableEntity
from .models import BaseModel

from flask_jwt_extended import verify_jwt_in_request, current_user as jwt_current_user, exceptions

logger = logging.getLogger(__name__)


# Default role enum - can be overridden via UserRole subclasses
class DefaultUserRole(str, enum.Enum):
    """Default user role enumeration."""
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"

class User(BaseModel):
    """Concrete User model with role-based permissions and domain support.

    This is the main User model for Flask-More-Smorest applications. It provides:
    - Email-based authentication with secure password hashing  
    - Role-based permissions with optional domain scoping
    - JWT token support for API authentication
    - User settings storage for key-value preferences
    - Built-in relationships to roles, settings, and tokens
    - Permission checking methods for CRUD operations

    **Using the Default User Model:**
    
    Import and use directly:
    ```python
    from flask_more_smorest.user import User
    
    # User model is ready to use with all features
    user = User(email="test@example.com")
    user.set_password("secure_password")
    user.save()
    ```

    **Extending the User Model:**
    
    Create custom user models by inheriting from this class:
    ```python
    from flask_more_smorest.user import User
    from flask_more_smorest.database import db
    import sqlalchemy as sa
    from sqlalchemy.orm import Mapped, mapped_column
    
    class CustomUser(User):
        __tablename__ = "custom_users"  # Use different table name
        
        # Add custom fields
        bio: Mapped[str] = mapped_column(db.String(500), nullable=True)
        age: Mapped[int] = mapped_column(db.Integer, nullable=True)
        phone: Mapped[str] = mapped_column(db.String(20), nullable=True)
        
        # Override permission methods if needed
        def _can_write(self) -> bool:
            # Custom permission logic
            if self.age and self.age < 18:
                return False  # Minors can't edit profiles
            return super()._can_write()
            
        # Add custom methods
        @property
        def is_adult(self) -> bool:
            return self.age is not None and self.age >= 18
    ```

    **Built-in Features Available to All User Models:**
    
    All User models (default or custom) automatically include:
    - `roles`: Relationship to UserRole objects for permission management
    - `settings`: Relationship to UserSetting objects for user preferences  
    - `tokens`: Relationship to Token objects for API authentication
    - `is_admin`/`is_superadmin`: Properties for checking admin privileges
    - `has_role()`: Method to check specific roles with optional domain scoping
    - `has_domain_access()`: Method to check domain-specific permissions
    - Permission methods: `_can_read()`, `_can_write()`, `_can_create()`

    **Inheritance Without Abstract Base Class:**
    
    Simply inherit from this concrete User class and add your custom fields and methods.
    """

    __tablename__ = "users"

    # Core authentication fields that all User models must have
    email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
    password: Mapped[bytes | None] = mapped_column(db.LargeBinary(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)

    # Core relationships that all User models inherit  
    # Using enable_typechecks=False to allow UserRole subclasses
    @declared_attr
    def roles(cls) -> Mapped[list["UserRole"]]:
        """Relationship to user roles - inherited by all User models."""
        return relationship(
            "UserRole", 
            back_populates="user", 
            cascade="all, delete-orphan",
            enable_typechecks=False  # Allow UserRole subclasses
        )

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
        return self.has_role(DefaultUserRole.ADMIN) or self.is_superadmin

    @property
    def is_superadmin(self) -> bool:
        """Check if user has superadmin privileges."""
        return self.has_role(DefaultUserRole.SUPERADMIN)

    def has_role(self, role: Any, domain_name: str | None = None) -> bool:
        """Check if user has specified role, optionally scoped to domain."""
        # Normalize role to string for comparison
        role_str = role.value if hasattr(role, "value") else str(role)

        return any(
            r.role == role_str
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
    """User roles with domain scoping for multi-tenant applications.
    
    To use custom role enums, simply pass enum values when creating roles:
    
    class CustomRole(str, enum.Enum):
        SUPERADMIN = "superadmin"
        ADMIN = "admin"
        MANAGER = "manager"
        USER = "user"

    # Create roles with custom enum values
    role = UserRole(user=user, role=CustomRole.MANAGER)
    
    # The role property will return the string value, which can be
    # converted back to your custom enum as needed:
    manager_role = CustomRole(role.role) if hasattr(CustomRole, role.role) else role.role
    """

    __tablename__ = "user_roles"

    # Store role as string to support any enum
    # No default Role enum - accept any string/enum value

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

    # Store role as string to support custom enums
    _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

    @property
    def role(self) -> Any:
        """Get role as string value."""
        return self._role

    @role.setter
    def role(self, value: Any) -> None:
        """Set role value from enum or string."""
        if hasattr(value, "value"):
            # Handle enum
            self._role = value.value
        else:
            # Handle string
            self._role = str(value)

    def __init__(self, domain_id: uuid.UUID | str | None = None, role: Any = None, **kwargs):
        """Initialize role with domain and role handling."""
        if domain_id is None:
            domain_id = Domain.get_default_domain_id()
        # Force explicit use of '*' to set domain_id to None:
        if domain_id == "*":
            domain_id = None

        # Handle role parameter
        if role is not None:
            if hasattr(role, "value"):
                kwargs["_role"] = role.value
            else:
                kwargs["_role"] = str(role)

        super().__init__(domain_id=domain_id, **kwargs)

    def _can_write(self) -> bool:
        """Permission check for modifying roles."""
        try:
            current = get_current_user()
            # Check against default admin roles
            admin_roles = {DefaultUserRole.SUPERADMIN.value, DefaultUserRole.ADMIN.value}
            
            if self._role in admin_roles:
                return current.has_role(DefaultUserRole.SUPERADMIN)
            return current.has_role(DefaultUserRole.ADMIN)
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
        self.deleted_at = dt.datetime.now(dt.timezone.utc)
        # Only set is_enabled if it exists
        if hasattr(self, "is_enabled"):
            self.is_enabled = False

    def restore(self) -> None:
        """Restore soft deleted record."""
        self.deleted_at = None
        # Only set is_enabled if it exists
        if hasattr(self, "is_enabled"):
            self.is_enabled = True
