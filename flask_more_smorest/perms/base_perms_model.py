"""Base permission-aware model for Flask-More-Smorest.

This module provides BasePermsModel which extends BaseModel with
permission checking functionality based on the current user context.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable

import sqlalchemy as sa
from flask import has_request_context
from flask_jwt_extended import exceptions, verify_jwt_in_request
from werkzeug.exceptions import Unauthorized

from ..error.exceptions import ForbiddenError, UnauthorizedError
from ..sqla import BaseModel as SQLABaseModel

if TYPE_CHECKING:
    from flask import Flask  # noqa: F401

logger = logging.getLogger(__name__)


class BasePermsModel(SQLABaseModel):
    """Permission-aware Base model for all models.

    This model extends BaseModel with permission checking based on the
    current authenticated user. It provides hooks for read, write, and
    create permission checks that subclasses can override.

    Attributes:
        perms_disabled: Whether permission checking is disabled (default: False)

    Example:
        >>> class Article(BasePermsModel):
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        ...
        ...     def _can_write(self) -> bool:
        ...         return self.user_id == get_current_user_id()
    """

    __abstract__ = True
    perms_disabled = False

    def __init__(self, **kwargs: object) -> None:
        """Initialize the model after checking that all sub fields can be created.

        Args:
            **kwargs: Field values to initialize the model with
        """

        self.check_create(kwargs.values())
        super().__init__(**kwargs)

    @classmethod
    @contextmanager
    def bypass_perms(cls) -> Iterator[None]:
        """Context manager to bypass permissions for the class.

        Temporarily disables permission checking for this model class.

        Yields:
            None

        Example:
            >>> with Article.bypass_perms():
            ...     article.delete()  # Deletes without permission check
        """
        original = cls.perms_disabled
        cls.perms_disabled = True
        try:
            yield
        finally:
            cls.perms_disabled = original

    def _should_bypass_perms(self) -> bool:
        """Check if permissions should be bypassed.

        Returns:
            True if permissions are disabled or not in request context
        """
        return self.perms_disabled or not has_request_context()

    def _execute_permission_check(self, check_func: Callable[[], bool], operation: str) -> bool:
        """Execute permission check with consistent error handling.

        Args:
            check_func: Permission check function to execute
            operation: Name of operation for logging (e.g., 'write', 'read')

        Returns:
            True if permission check passes, False otherwise

        Raises:
            UnauthorizedError: If user authentication is required
        """
        try:
            return check_func()
        except RuntimeError:
            raise UnauthorizedError("User must be authenticated")
        except Exception as e:
            logger.error("can_%s() exception: %s", operation, e)
            return False

    def can_write(self) -> bool:
        """Does current user have write permission on object.

        Returns:
            True if user can write, False otherwise
        """
        if self._should_bypass_perms():
            return True

        is_admin = getattr(self, "is_admin", False)
        is_role_instance = type(self).__name__ == "UserRole"
        if not is_role_instance and not is_admin and self.is_current_user_admin():
            return True

        if getattr(sa.inspect(self), "transient", False):
            return self._execute_permission_check(self._can_create, "create")
        return self._execute_permission_check(self._can_write, "write")

    def can_read(self) -> bool:
        """Does current user have read permissions on object.

        Returns:
            True if user can read, False otherwise
        """
        if self._should_bypass_perms():
            return True

        if self.id is None or self.is_current_user_admin():
            return True

        return self._execute_permission_check(self._can_read, "read")

    def can_create(self) -> bool:
        """Can current user create object.

        Returns:
            True if user can create, False otherwise
        """

        if self.perms_disabled or not has_request_context():
            return True
        is_admin = getattr(self, "is_admin", False)
        is_role_instance = type(self).__name__ == "UserRole"
        if not is_role_instance and not is_admin and self.is_current_user_admin():
            return True

        return self._can_create()

    def _can_write(self) -> bool:
        """Permission helper: override in subclasses.

        Returns:
            False (deny by default, must be explicitly allowed in subclasses)
        """
        return False

    def _can_create(self) -> bool:
        """Permission helper: override in subclasses.

        Returns:
            True (allow creation by default)
        """
        return True  # adding new records is allowed by default

    def _can_read(self) -> bool:
        """Permission helper: override in subclasses.

        Returns:
            Same as _can_write() by default
        """
        return self._can_write()

    @classmethod
    def is_current_user_admin(cls) -> bool:
        """Check if current user is an admin.

        Returns:
            True if current user is admin, False otherwise
        """
        from .user_models import current_user

        try:
            verify_jwt_in_request()
            if current_user.is_admin:
                return True
        except exceptions.JWTExtendedException:
            return False
        except Unauthorized:
            return False

        return False

    def check_create(self, val: list | set | tuple | object) -> None:
        """Recursively check that all BaseModel instances can be created.

        Args:
            val: Value or collection of values to check

        Raises:
            ForbiddenError: If any nested object cannot be created
        """
        if isinstance(val, BasePermsModel):
            if getattr(sa.inspect(val), "transient", False) and not val.can_create():
                raise ForbiddenError(f"User not allowed to create resource: {val}")
        elif isinstance(val, list) or isinstance(val, set) or isinstance(val, tuple):
            for x in val:
                self.check_create(x)
