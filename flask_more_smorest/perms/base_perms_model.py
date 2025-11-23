"""Base permission-aware model for Flask-More-Smorest.

This module provides BasePermsModel which extends BaseModel with
permission checking functionality based on the current user context.
"""

from contextlib import contextmanager
from collections.abc import Iterator
from typing import TYPE_CHECKING

from flask import has_request_context
from flask_jwt_extended import verify_jwt_in_request, exceptions
from werkzeug.exceptions import Unauthorized

from ..error.exceptions import ForbiddenError, UnauthorizedError
from ..sqla import db, BaseModel as SQLABaseModel

if TYPE_CHECKING:
    from flask import Flask


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

    def __init__(self, **kwargs: str | int | float | bool | bytes | None) -> None:
        """Initialize the model after checking that all sub fields can be created.

        Args:
            **kwargs: Field values to initialize the model with
        """

        self.check_create(kwargs.values())
        super().__init__(**kwargs)

    @classmethod
    @contextmanager
    def bypass_perms(cls_self) -> Iterator[None]:
        """Context manager to bypass permissions for the class.

        Temporarily disables permission checking for this model class.

        Yields:
            None

        Example:
            >>> with Article.bypass_perms():
            ...     article.delete()  # Deletes without permission check
        """
        original = cls_self.perms_disabled
        cls_self.perms_disabled = True
        try:
            yield
        finally:
            cls_self.perms_disabled = original

    def can_write(self) -> bool:
        """Does current user have write permission on object.

        Returns:
            True if user can write, False otherwise
        """

        if self.perms_disabled or not has_request_context():
            return True

        is_admin = getattr(self, "is_admin", False)
        is_role_instance = type(self).__name__ == "UserRole"
        if not is_role_instance and not is_admin and self.is_current_user_admin():
            return True

        try:
            if self.id is None:
                return self._can_create()
            return self._can_write()
        except RuntimeError:
            raise UnauthorizedError("User must be authenticated")
        except Exception as e:
            print("DEBUG: can_write() ***EXCEPTION:", e)
            pass

        return False

    def can_read(self) -> bool:
        """Does current user have read permissions on object.

        Returns:
            True if user can read, False otherwise
        """

        if self.perms_disabled or not has_request_context():
            return True

        if self.id is None or self.is_current_user_admin():
            return True
        try:
            if self._can_read():
                return True
        except RuntimeError:
            raise UnauthorizedError("User must be authenticated")
        except Exception as e:
            print("DEBUG: can_read() ***EXCEPTION:", e)
            pass

        return False

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

    def check_create(self, val: object) -> None:
        """Recursively check that all BaseModel instances can be created.

        Args:
            val: Value or collection of values to check

        Raises:
            ForbiddenError: If any nested object cannot be created
        """
        for x in val:
            if isinstance(x, BasePermsModel):
                if x.id is None and not x.can_create():
                    raise ForbiddenError(f"User not allowed to create resource: {x}")
            elif isinstance(x, list):
                self.check_create(x)
