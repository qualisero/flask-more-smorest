"""Enhanced Blueprint with additional decorators and functionality.

This module provides BlueprintOperationIdMixin that extends Flask-Smorest's
Blueprint to automatically generate OpenAPI operationId values for endpoints.
"""

import functools
from typing import Callable, Final

from flask.views import MethodView
from flask_smorest import Blueprint

from .utils import convert_snake_to_camel

HTTP_METHOD_OPERATION_MAP: Final[dict[str, str]] = {
    "patch": "update",
    "delete": "delete",
    "get": "get",
    "post": "create",
    "put": "replace",
}

__all__ = ["BlueprintOperationIdMixin", "HTTP_METHOD_OPERATION_MAP"]


class BlueprintOperationIdMixin(Blueprint):
    """Blueprint mixin that provides automatic operationId generation.

    This mixin extends Flask-Smorest's Blueprint to automatically generate
    OpenAPI operationId values for routes based on the route pattern and
    HTTP method. This provides consistent naming for API operations.

    Example:
        >>> class MyBlueprint(BlueprintOperationIdMixin):
        ...     pass
        >>> bp = MyBlueprint('users', __name__)
        >>> @bp.route('/')
        >>> class UserList(MethodView):
        ...     def get(self):  # operationId: listUser
        ...         pass
    """

    def route(
        self, rule: str, *pargs: str, **kwargs: bool | str
    ) -> Callable[[type["MethodView"] | Callable], type["MethodView"] | Callable]:
        """Override route to add automatic operationId.

        Args:
            rule: URL rule for the route
            *pargs: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Decorated route function or MethodView class
        """
        wrapped: Callable[[type["MethodView"] | Callable], type["MethodView"] | Callable] = super().route(
            rule, *pargs, **kwargs
        )

        def _add_operation_id(func: Callable, method_view_class: type["MethodView"] | None = None) -> Callable:
            """Add operationId to the function if not already set.

            Args:
                func: The endpoint function to add operationId to
                method_view_class: The MethodView class if applicable

            Returns:
                The function with operationId added
            """
            apidoc: dict[str, dict[str, str]] = getattr(func, "_apidoc", {})
            if "manual_doc" in apidoc and "operationId" in apidoc["manual_doc"]:
                return func
            method_name = func.__name__.lower()
            if method_view_class is None:
                operation_id = func.__name__
            else:
                class_name = method_view_class.__name__
                # TODO: decide if ending in `/` should be enough to consider it a collection
                if method_name == "get" and class_name.endswith("s") and rule.endswith("/"):
                    operation_id = f"list{class_name}"
                else:
                    operation_name = HTTP_METHOD_OPERATION_MAP.get(method_name, method_name)
                    operation_id = f"{operation_name}{class_name}"
            operation_id = convert_snake_to_camel(operation_id)
            operation_id = operation_id[0].lower() + operation_id[1:]
            decorated_func = self.doc(operationId=operation_id)(func)
            # Use functools.wraps to preserve the function signature
            return functools.wraps(func)(decorated_func)

        def _route(class_or_func: type["MethodView"] | Callable) -> type["MethodView"] | Callable:
            """Add operationId to the route's methods.

            Args:
                class_or_func: The MethodView class or function to decorate

            Returns:
                The decorated class or function
            """
            if isinstance(class_or_func, type) and issubclass(class_or_func, MethodView):
                for method in class_or_func.methods or []:
                    method_fn: Callable | None = getattr(class_or_func, method.lower(), None)
                    if not method_fn:
                        continue
                    method_fn = _add_operation_id(method_fn, class_or_func)
                    setattr(class_or_func, method.lower(), method_fn)
            else:
                class_or_func = _add_operation_id(class_or_func)
            return wrapped(class_or_func)

        return _route
