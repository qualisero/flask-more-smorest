"""Base permission-aware model for Flask-More-Smorest."""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Self, cast

import sqlalchemy as sa
from flask import has_request_context
from flask_jwt_extended import exceptions
from sqlalchemy.orm.state import InstanceState
from werkzeug.exceptions import Unauthorized

from flask_more_smorest.perms.user_context import ROLE_ADMIN, ROLE_SUPERADMIN

from ..error.exceptions import ForbiddenError, UnauthorizedError
from ..sqla import BaseModel as SQLABaseModel

logger = logging.getLogger(__name__)


class BasePermsModel(SQLABaseModel):
    """Base model with permission checking.

    Attributes:
        perms_disabled: Disable permission checks (default: False)

    Example:
        >>> class Article(BasePermsModel):
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        ...     def _can_write(self, user) -> bool:
        ...         return user is not None and self.user_id == user.id
    """

    __abstract__ = True
    perms_disabled = False

    def __init__(self, **kwargs: object) -> None:
        """Initialize model after checking sub-fields can be created."""
        from .user_registry import ensure_models_initialized

        ensure_models_initialized()
        self.check_create(kwargs.values())
        super().__init__(**kwargs)

    @classmethod
    @contextmanager
    def bypass_perms(cls) -> Iterator[None]:
        """Temporarily disable permission checking for this model class.

        Example:
            >>> with Article.bypass_perms():
            ...     article.delete()  # No permission check
        """
        original = cls.perms_disabled
        cls.perms_disabled = True
        try:
            yield
        finally:
            cls.perms_disabled = original

    def _should_bypass_perms(self) -> bool:
        return self.perms_disabled or not has_request_context()

    def _check_admin_bypass(self, user: Any) -> bool:
        """Check if current operation should bypass due to admin privileges.

        Returns True if:
        - Permissions are disabled (bypass_perms context)
        - Not in request context
        - Current user is admin AND target is not admin-protected

        Returns:
            True if permission check should be skipped
        """
        if self._should_bypass_perms():
            return True

        # UserRole has special admin rules
        if type(self).__name__ == "UserRole":
            return False

        # Don't auto-allow if target has is_admin=True
        if getattr(self, "is_admin", False):
            return False

        return user is not None and (user.has_role(ROLE_ADMIN) or user.has_role(ROLE_SUPERADMIN))

    def _execute_permission_check(self, check_func: Callable[[], bool], operation: str) -> bool:
        """Execute permission check with consistent error handling.

        Args:
            check_func: Permission check function
            operation: Operation name for logging

        Returns:
            True if permission check passes

        Raises:
            UnauthorizedError: If user authentication is required
        """
        try:
            return check_func()
        except (exceptions.JWTExtendedException, Unauthorized):
            raise UnauthorizedError("User must be authenticated")
        except RuntimeError as e:
            if not has_request_context():
                raise UnauthorizedError("User must be authenticated")
            raise e

    def can_write(self, user: Any = None) -> bool:
        """Check if current user has write permission."""

        if user is None:
            from .user_context import get_current_user

            user = get_current_user()

        if self._check_admin_bypass(user):
            return True

        if getattr(sa.inspect(self), "transient", False):
            return self._execute_permission_check(lambda: self._can_create(user), "create")

        return self._execute_permission_check(lambda: self._can_write(user), "write")

    def can_read(self, user: Any = None) -> bool:
        """Check if current user has read permission."""

        if user is None:
            from .user_context import get_current_user

            user = get_current_user()

        if self._check_admin_bypass(user):
            return True

        if self.id is None:
            return True  # type: ignore[unreachable]  # mypy false positive

        return self._execute_permission_check(lambda: self._can_read(user), "read")

    def can_create(self, user: Any = None) -> bool:
        """Check if current user can create objects."""

        if user is None:
            from .user_context import get_current_user

            user = get_current_user()

        if self._check_admin_bypass(user):
            return True

        return self._execute_permission_check(lambda: self._can_create(user), "create")

    def _can_write(self, user: Any) -> bool:
        """Internal permission check for write/update/delete operations.

        This method MUST be overridden by subclasses to define write permissions.
        It is called by the public `can_write()` and `delete()` methods.

        Args:
            user: The currently authenticated user object (or None)

        Returns:
            bool: True if operation is allowed, False otherwise.
                  Defaults to False (deny all) for safety.
        """
        return False

    def _can_create(self, user: Any) -> bool:
        """Internal permission check for creation operations.

        This method SHOULD be overridden by subclasses if create logic differs
        from default (allow all). It is called by `can_create()` and `save()`.

        Args:
            user: The currently authenticated user object (or None)

        Returns:
            bool: True if creation is allowed, False otherwise.
                  Defaults to True (allow all).
        """
        return True

    def _can_read(self, user: Any) -> bool:
        """Internal permission check for read operations.

        This method SHOULD be overridden by subclasses.
        It is called by `can_read()` and `get_by()`.

        Args:
            user: The currently authenticated user object (or None)

        Returns:
            bool: True if read is allowed, False otherwise.
                  Defaults to calling `_can_write()` (if you can write, you can read).
        """
        return self._can_write(user)

    def _check_permission(self, operation: str) -> None:
        """Ensure permissions exist before mutating resource.

        Logs permission denials at WARNING level for debugging.

        Args:
            operation: Operation type ('write', 'create', 'delete')

        Raises:
            ForbiddenError: If user doesn't have permission
        """
        from .user_context import get_current_user_id

        permission_methods = {
            "write": (self.can_write, "modify"),
            "create": (self.can_create, "create"),
            "delete": (self.can_write, "delete"),
        }
        check_method, action = permission_methods[operation]
        if not check_method():
            user_id = get_current_user_id()

            # Determine the reason for permission failure
            reason = self._get_permission_failure_reason(operation)

            logger.warning(
                "Permission denied: user %s cannot %s %s (id=%s): %s",
                user_id,
                action,
                self.__class__.__name__,
                self.id,
                reason or "permission denied",
            )

            raise ForbiddenError(
                operation=action,
                resource_type=self.__class__.__name__,
                resource_id=self.id,
                reason=reason,
                user_id=str(user_id) if user_id else None,
            )

    def _get_permission_failure_reason(self, operation: str) -> str | None:
        """Determine the reason for permission failure.

        Override in subclasses to provide specific failure reasons.

        Args:
            operation: Operation type ('write', 'create', 'delete')

        Returns:
            Human-readable reason string, or None for generic denial

        Example:
            >>> def _get_permission_failure_reason(self, operation: str) -> str | None:
            ...     from .user_context import get_current_user
            ...     user = get_current_user()
            ...     if user is None:
            ...         return "not authenticated"
            ...     if operation == "write" and self.published:
            ...         return "cannot modify published articles"
            ...     return None
        """
        from .user_context import get_current_user

        user = get_current_user()
        if user is None:
            return "not authenticated"
        return None  # Generic "permission denied"

    def save(self, commit: bool = True) -> Self:
        """Extend BaseModel save with permission checks."""
        state = cast(InstanceState[Any], sa.inspect(self))
        if getattr(state, "transient", False) or getattr(state, "pending", False):
            self._check_permission("create")
        else:
            self._check_permission("write")
        return super().save(commit=commit)

    def delete(self, commit: bool = True) -> None:
        """Extend BaseModel delete with permission checks."""
        self._check_permission("delete")
        return super().delete(commit=commit)

    @classmethod
    def get_by(cls, **kwargs: Any) -> Self | None:
        """Get resource by field values with permission check.

        Returns:
            Instance if found and can_read() is True
            None if not found
            None if found but can_read() is False and RETURN_404_ON_ACCESS_DENIED is True
        Raises:
            ForbiddenError: If found but can_read() is False
        """
        from flask import current_app

        res = super().get_by(**kwargs)
        if res is None:
            return None

        if res.can_read():
            return res

        if current_app and current_app.config.get("RETURN_404_ON_ACCESS_DENIED"):
            return None

        raise ForbiddenError(f"User not allowed to read resource: {res}")

    def check_create(self, val: list | set | tuple | object, _visited: set[int] | None = None) -> None:
        """Recursively check that all BaseModel instances can be created.

        Args:
            val: Value or collection of values to check
            _visited: Internal set of visited object IDs to prevent infinite recursion

        Raises:
            ForbiddenError: If any nested object cannot be created
        """
        if _visited is None:
            _visited = set()

        obj_id = id(val)
        if obj_id in _visited:
            return
        _visited.add(obj_id)

        if isinstance(val, BasePermsModel):
            if getattr(sa.inspect(val), "transient", False) and not val.can_create():
                raise ForbiddenError(f"User not allowed to create resource: {val}")
        elif isinstance(val, list | set | tuple):
            for x in val:
                self.check_create(x, _visited=_visited)
