"""Blueprint Mixin to support method annotation for access control.

This module provides PermsBlueprintMixin which adds decorators for marking
endpoints as public or admin-only.
"""

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable as CallableType


class PermsBlueprintMixin:
    """Blueprint mixin with added annotations for public and admin endpoints.

    This mixin extends Flask-Smorest's Blueprint to provide additional
    decorators for marking endpoints with special access levels:
    - public_endpoint: Accessible without authentication
    - admin_endpoint: Requires admin privileges

    Example:
        >>> class MyBlueprint(Blueprint, PermsBlueprintMixin):
        ...     pass
        >>> bp = MyBlueprint('items', __name__)
        >>> @bp.route('/')
        >>> @bp.public_endpoint
        >>> def list_items():
        ...     return []
    """

    def public_endpoint(self, function: Callable) -> Callable:
        """Decorator to mark an endpoint as public.

        Public endpoints do not require authentication and can be
        accessed by anyone.

        Args:
            function: The endpoint function to mark as public

        Returns:
            The decorated function with public annotation

        Example:
            >>> @bp.route('/health')
            >>> @bp.public_endpoint
            >>> def health_check():
            ...     return {'status': 'ok'}
        """
        function._is_public = True
        if function.__doc__ is None:
            function.__doc__ = "Public endpoint"
        else:
            function.__doc__ += " | 🌐 Public"
        return function

    def admin_endpoint(self, func: Callable) -> Callable:
        """Decorator to mark an endpoint as admin only.

        Admin endpoints require the user to have admin privileges.
        The Api class enforces this during request handling.

        Args:
            func: The endpoint function to mark as admin only

        Returns:
            The decorated function with admin annotation

        Example:
            >>> @bp.route('/users/<uuid:user_id>')
            >>> @bp.admin_endpoint
            >>> def delete_user(user_id):
            ...     # Only admins can delete users
            ...     pass
        """
        func._is_admin = True
        if func.__doc__ is None:
            func.__doc__ = "Admin only endpoint"
        else:
            func.__doc__ += " | 🔑 Admin only"
        return func
