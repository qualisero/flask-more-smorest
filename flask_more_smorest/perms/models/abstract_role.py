"""Abstract role and domain models for Flask-More-Smorest.

Provides abstract bases for Domain and UserRole models for
multi-domain role-based access control.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base_perms_model import BasePermsModel

if TYPE_CHECKING:
    from .abstract_user import AbstractUser


class AbstractDomain(BasePermsModel):
    """Abstract Domain model for multi-domain support.

    This is an abstract base class - it does NOT create a database table.
    Subclasses must define concrete fields and table configuration.

    Domains represent distinct contexts within an application (e.g.,
    organizations, tenants, or projects) where roles can be scoped.

    **Subclassing example:**

    .. code-block:: python

        from flask_more_smorest.perms import AbstractDomain

        class CustomDomain(AbstractDomain):
            __tablename__ = "domain"

            name: Mapped[str] = mapped_column(db.String(255), nullable=False)
            display_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
            active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)

            # Optional: custom fields
            organization_id: Mapped[str] = mapped_column(db.String(50))
            settings: Mapped[dict] = mapped_column(db.JSON, default={})
    """

    __abstract__ = True  # No table is created
    __tablename__ = "domain"
    __table_args__ = {"extend_existing": True}  # noqa: RUF012

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean(), default=True, nullable=False)


class AbstractUserRole(BasePermsModel):
    """Abstract UserRole model with domain scoping for multi-domain applications.

    This is an abstract base class - it does NOT create a database table.
    Subclasses must define concrete fields and table configuration.

    Supports custom role enums by accepting any string/enum value:

    .. code-block:: python

        from enum import Enum

        class CustomRole(str, Enum):
            SUPERADMIN = "SUPERADMIN"
            ADMIN = "ADMIN"
            MANAGER = "MANAGER"
            USER = "USER"

        class CustomUserRole(AbstractUserRole):
            __tablename__ = "user_role"

            user_id: Mapped[uuid.UUID] = mapped_column(
                sa.Uuid(as_uuid=True),
                db.ForeignKey("user.id"),
                nullable=False
            )
            domain_id: Mapped[uuid.UUID | None] = mapped_column(
                sa.Uuid(as_uuid=True),
                db.ForeignKey("domain.id"),
                nullable=True,
                default=None,
            )
            _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

        # Create roles with custom enum values
        role = CustomUserRole(user=user, role=CustomRole.MANAGER)
    """

    __abstract__ = True  # No table is created
    __tablename__ = "user_role"
    __table_args__ = {"extend_existing": True}  # noqa: RUF012

    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), sa.ForeignKey("user.id"), nullable=False)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("domain.id"),
        nullable=True,
        default=None,
    )
    _role: Mapped[str] = mapped_column("role", sa.String(50), nullable=False)

    @declared_attr
    def user(cls) -> Mapped[AbstractUser]:
        from ..user_registry import get_user_model

        return relationship(
            lambda: get_user_model(),
            back_populates="roles",
            enable_typechecks=False,
        )

    @declared_attr
    def domain(cls) -> Mapped[AbstractDomain | None]:
        from ..user_registry import get_domain_model

        return relationship(lambda: get_domain_model())

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
        self._role = self._normalise_role(value)

    def __init__(
        self,
        domain_id: uuid.UUID | str | None = None,
        role: str | enum.Enum | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize role with domain and role handling.

        Args:
            domain_id: Domain UUID, None for all domains, or '*' string (converted to None)
            role: Role value (enum or string)
            **kwargs: Additional field values
        """
        # Note: domain_id is no longer defaulted here - user must provide it explicitly
        # Force explicit use of '*' to set domain_id to None:
        if domain_id == "*":
            domain_id = None
        if isinstance(domain_id, str):
            raise TypeError("Expected domain_id to be UUID, None or '*'")

        # Handle role parameter - normalize to uppercase
        if role is not None:
            kwargs["_role"] = self._normalise_role(role)

        super().__init__(domain_id=domain_id, **kwargs)

    def _normalise_role(self, role: str | enum.Enum) -> str:
        """Normalize role value for consistent comparisons.

        Returns:
            Normalized role string
        """
        if isinstance(role, enum.Enum):
            return str(role.value).upper()
        return str(role).upper()
