"""Role and domain models for Flask-More-Smorest.

Provides DefaultUserRole enum, Domain, and UserRole models for
multi-domain role-based access control.
"""

from __future__ import annotations

import enum
import os
import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...sqla import db
from ..base_perms_model import BasePermsModel

if TYPE_CHECKING:
    from .user import User


class DefaultUserRole(str, enum.Enum):
    """Default user role enumeration."""

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class Domain(BasePermsModel):
    """Distinct domains within the app for multi-domain support."""

    __mapper_args__ = {
        "polymorphic_on": "discriminator",
        "polymorphic_identity": "domain",
    }

    discriminator: Mapped[str] = mapped_column(
        db.String(50),
        default="domain",
        nullable=False,
        server_default="domain",
    )

    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)

    @classmethod
    def get_default_domain_id(cls) -> uuid.UUID | None:
        """Get the default domain ID from environment or first available."""
        domain: Domain | None
        if default_domain := os.getenv("DEFAULT_DOMAIN_NAME"):
            domain = cls.get_by(name=default_domain)
            if domain:
                return domain.id
        domain = db.session.execute(sa.select(cls).limit(1)).scalar_one_or_none()
        if domain:
            return domain.id
        return None

    def _can_read(self, current_user: Any) -> bool:
        """Any user can read domains.

        Args:
            current_user: The current authenticated user, or None (ignored for Domain)
        """
        return True


class UserRole(BasePermsModel):
    """User roles with domain scoping for multi-domain applications.

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

    # Store role as string to support any enum
    # No default Role enum - accept any string/enum value

    # Use string reference for User to support custom models
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey("user.id"), nullable=False)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        db.ForeignKey("domain.id"),
        nullable=True,
        default=None,
    )

    # Relationships
    domain: Mapped[Domain | None] = relationship("Domain")
    user: Mapped[User] = relationship(
        "User",  # Use string reference to avoid circular import
        back_populates="roles",
        enable_typechecks=False,  # allow User subclasses
    )

    # Store role as string to support custom enums
    _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

    @property
    def role(self) -> str:
        """Get role as string value.

        Returns:
            Role name as string
        """
        return self._role

    @role.setter
    def role(self, value: str | enum.Enum) -> None:
        """Set role value from enum or string.

        Args:
            value: Role value (enum or string)
        """
        # Normalize role to string for comparison
        self._role = value.value if isinstance(value, enum.Enum) else str(value)

    def __init__(
        self,
        domain_id: uuid.UUID | str | None = None,
        role: str | enum.Enum | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize role with domain and role handling.

        Args:
            domain_id: Domain UUID or '*' for all domains
            role: Role value (enum or string)
            **kwargs: Additional field values
        """
        if domain_id is None:
            domain_id = Domain.get_default_domain_id()
        # Force explicit use of '*' to set domain_id to None:
        elif domain_id == "*":
            domain_id = None
        if isinstance(domain_id, str):
            raise TypeError("Expected domain_id to be UUID, None or '*'")

        # Handle role parameter
        if role is not None:
            kwargs["_role"] = role.value if isinstance(role, enum.Enum) else str(role)

        super().__init__(domain_id=domain_id, **kwargs)

    def _can_write(self, current_user: Any) -> bool:
        """Permission check for modifying roles.

        Supports custom role enums by checking for elevated role names
        ('superadmin' or 'admin' in the role string).

        Args:
            current_user: The current authenticated user, or None
        """
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        try:
            if not current_user:
                return False

            # Superadmins can modify any role
            if current_user.has_role(ROLE_SUPERADMIN):
                return True

            # Admins can only modify non-admin roles
            # Conservative string check: assume "admin" or "superadmin" in role name means elevated
            role_value = self._role.lower()
            is_elevated_role = "superadmin" in role_value or "admin" in role_value

            return not is_elevated_role and current_user.has_role(ROLE_ADMIN)
        except Exception:
            return False

    def _can_create(self, current_user: Any) -> bool:
        """Permission check for creating roles.

        Uses same logic as _can_write(): only superadmins can create
        admin/superadmin roles, admins can create other roles.

        Args:
            current_user: The current authenticated user, or None
        """
        return self._can_write(current_user)

    def _can_read(self, current_user: Any) -> bool:
        """Permission check for reading roles.

        Args:
            current_user: The current authenticated user, or None
        """
        try:
            return self.user._can_read(current_user)
        except Exception:
            return True
