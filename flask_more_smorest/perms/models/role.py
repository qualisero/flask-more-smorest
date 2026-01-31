"""Role and domain models for Flask-More-Smorest.

Provides BaseRoleEnum, Domain, and UserRole models for
multi-domain role-based access control.
"""

from __future__ import annotations

import enum
import os
import uuid
from typing import Any

import sqlalchemy as sa

from ...sqla import db
from .abstract_role import AbstractDomain, AbstractUserRole
from .base_roles import BaseRoleEnum

__all__ = ["BaseRoleEnum", "Domain", "UserRole"]


class Domain(AbstractDomain):
    """Distinct domains within the app for multi-domain support.

    This is a concrete implementation of AbstractDomain. For customization,
    subclass AbstractDomain instead of this class.
    """

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

    def _can_read(self, user: Any) -> bool:
        """Any user can read domains.

        Args:
            user: The current authenticated user, or None (ignored for Domain)
        """
        return True


class UserRole(AbstractUserRole):
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
        # Normalize role to uppercase string for consistency
        # This handles both enum values (already uppercase) and string inputs
        if isinstance(value, enum.Enum):
            self._role = str(value.value).upper()
        else:
            self._role = str(value).upper()

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

        # Handle role parameter - normalize to uppercase
        if role is not None:
            if isinstance(role, enum.Enum):
                kwargs["_role"] = str(role.value).upper()
            else:
                kwargs["_role"] = str(role).upper()

        super().__init__(domain_id=domain_id, role=role, **kwargs)

    def _can_write(self, user: Any) -> bool:
        """Permission check for modifying roles.

        Supports custom role enums by checking for elevated role names
        ('superadmin' or 'admin' in the role string).

        Args:
            user: The current authenticated user, or None
        """
        from ..user_context import ROLE_ADMIN, ROLE_SUPERADMIN

        try:
            if not user:
                return False

            # Superadmins can modify any role
            if user.has_role(ROLE_SUPERADMIN):
                return True

            # Admins can only modify non-admin roles
            # Check for elevated role names (uppercase) in stored role
            role_value = self._role.upper()
            is_elevated_role = "SUPERADMIN" in role_value or "ADMIN" in role_value

            return not is_elevated_role and user.has_role(ROLE_ADMIN)
        except Exception:
            return False

    def _can_create(self, user: Any) -> bool:
        """Permission check for creating roles.

        Uses same logic as _can_write(): only superadmins can create
        admin/superadmin roles, admins can create other roles.

        Args:
            user: The current authenticated user, or None
        """
        return self._can_write(user)

    def _can_read(self, user: Any) -> bool:
        """Permission check for reading roles.

        Delegates to user.can_read() to properly apply admin bypass logic.

        Args:
            user: The current authenticated user, or None
        """
        try:
            # Use can_read() instead of _can_read() to apply admin bypass logic
            return self.user.can_read(user)
        except Exception:
            return True
