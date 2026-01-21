"""Protocol definitions for Flask-More-Smorest.

These protocols define the interfaces that components expect,
allowing for loose coupling between modules and better type safety.

Protocols provide structural typing (duck typing with type checking),
enabling components to work with any object that has the required
attributes and methods, without requiring inheritance.

Example:
    >>> from flask_more_smorest.protocols import Identifiable, PermissionAware
    >>>
    >>> def process_item(item: Identifiable & PermissionAware) -> None:
    ...     if item.can_read():
    ...         print(f"Processing item {item.id}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from typing import Self


@runtime_checkable
class Identifiable(Protocol):
    """Object with an ID attribute.

    Any object that has an `id` attribute can satisfy this protocol,
    making it useful for generic functions that work with identified resources.

    Example:
        >>> def get_resource_id(resource: Identifiable) -> UUID | Any:
        ...     return resource.id
    """

    @property
    def id(self) -> UUID | Any:
        """Return the object's identifier."""
        ...


@runtime_checkable
class PermissionAware(Protocol):
    """Object with permission checking methods.

    Defines the interface for objects that support permission-based
    access control. Any object implementing these methods can be
    used in permission-aware contexts.

    Example:
        >>> def safe_update(obj: PermissionAware, **kwargs: Any) -> None:
        ...     if obj.can_write():
        ...         obj.update(**kwargs)
    """

    def can_read(self) -> bool:
        """Check if current user can read this object."""
        ...

    def can_write(self) -> bool:
        """Check if current user can write this object."""
        ...

    def can_create(self) -> bool:
        """Check if current user can create this object."""
        ...


@runtime_checkable
class Saveable(Protocol):
    """Object that can be persisted to a database.

    Defines the interface for objects with CRUD operations.

    Example:
        >>> def persist(obj: Saveable) -> None:
        ...     obj.save(commit=True)
    """

    def save(self, commit: bool = True) -> Self:
        """Save the object to the database.

        Args:
            commit: Whether to commit the transaction immediately

        Returns:
            The saved object (for method chaining)
        """
        ...

    def delete(self, commit: bool = True) -> None:
        """Delete the object from the database.

        Args:
            commit: Whether to commit the transaction immediately
        """
        ...


@runtime_checkable
class Updatable(Protocol):
    """Object that can be updated with new field values.

    Example:
        >>> def apply_changes(obj: Updatable, changes: dict[str, Any]) -> None:
        ...     obj.update(**changes)
    """

    def update(self, commit: bool = True, **kwargs: Any) -> None:
        """Update the object with new field values.

        Args:
            commit: Whether to commit the transaction immediately
            **kwargs: Field values to update
        """
        ...


@runtime_checkable
class CRUDModel(Identifiable, PermissionAware, Saveable, Updatable, Protocol):
    """Full CRUD model interface.

    Combines all the basic protocols to define a complete model interface
    with identification, permissions, and persistence operations.

    This is the most complete protocol and represents what most model
    classes in Flask-More-Smorest should implement.

    Example:
        >>> def process_model(model: CRUDModel) -> None:
        ...     if model.can_write():
        ...         model.update(status='processed')
        ...         model.save()
    """

    @classmethod
    def get_by(cls, **kwargs: Any) -> Self | None:
        """Get instance by field values.

        Args:
            **kwargs: Field name/value pairs to filter by

        Returns:
            Instance if found, None otherwise
        """
        ...

    @classmethod
    def get_by_or_404(cls, **kwargs: Any) -> Self:
        """Get instance by field values or raise 404.

        Args:
            **kwargs: Field name/value pairs to filter by

        Returns:
            Instance if found

        Raises:
            NotFoundError: If no instance is found
        """
        ...


@runtime_checkable
class UserLike(Protocol):
    """User-like object for permission checking.

    This protocol defines the minimal interface that permission checking
    code expects from user objects. Any user class (built-in or custom)
    that implements these methods can be used with the permissions system.

    Example:
        >>> def check_access(user: UserLike, resource: str) -> bool:
        ...     return user.has_role('admin') or user.has_role('superadmin')
    """

    @property
    def id(self) -> UUID | Any:
        """User identifier."""
        ...

    @property
    def is_admin(self) -> bool:
        """Whether user has admin privileges."""
        ...

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role.

        Args:
            role: Role name to check

        Returns:
            True if user has the role, False otherwise
        """
        ...

    def list_roles(self) -> list[str]:
        """List all roles the user has.

        Returns:
            List of role names as strings
        """
        ...


@runtime_checkable
class Timestamped(Protocol):
    """Object with automatic timestamp tracking.

    Example:
        >>> def get_creation_time(obj: Timestamped) -> Any:
        ...     return obj.created_at
    """

    @property
    def created_at(self) -> Any:
        """Timestamp of creation."""
        ...

    @property
    def updated_at(self) -> Any:
        """Timestamp of last update."""
        ...
