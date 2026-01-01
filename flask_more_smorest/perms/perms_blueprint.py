"""Blueprint Mixin to support method annotation for access control.

This module provides PermsBlueprintMixin which adds decorators for marking
endpoints as public or admin-only.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from flask.views import MethodView

if TYPE_CHECKING:
    from ..crud.crud_blueprint import MethodConfig


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

    def _configure_endpoint(
        self,
        view_cls: type[MethodView],
        method_name: str,
        docstring: str,
        method_config: "MethodConfig",
    ) -> None:
        """Configure endpoint admin decorator if needed.

        Args:
            view_cls: MethodView class containing the endpoint
            method_name: Name of the method to configure
            docstring: Docstring to set on the method
            method_config: Configuration dict for the method
        """
        # TODO: test that method from both CRUDBlueprint and PermsBlueprintMixin are called
        if hasattr(view_cls, method_name) and method_config.get("admin_only", False):
            method = getattr(view_cls, method_name)
            self.admin_endpoint(method)

    def public_endpoint(self, func: Callable) -> Callable:
        """Decorator to mark an endpoint as public.

        Public endpoints do not require authentication and can be
        accessed by anyone.

        Args:
            func: The endpoint function to mark as public

        Returns:
            The decorated function with public annotation

        Example:
            >>> @bp.route('/health')
            >>> @bp.public_endpoint
            >>> def health_check():
            ...     return {'status': 'ok'}
        """
        setattr(func, "_is_public", True)
        if func.__doc__ is None:
            func.__doc__ = "Public endpoint"
        else:
            func.__doc__ += " | 🌐 Public"
        return func

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
        setattr(func, "_is_admin", True)
        if func.__doc__ is None:
            func.__doc__ = "Admin only endpoint"
        else:
            func.__doc__ += " | 🔑 Admin only"
        return func
