from functools import wraps
from typing import Any

from flask_smorest.pagination import PaginationParameters


class CRUDPaginationMixin:
    """Mixin class to add custom pagination support to CRUDBlueprint."""

    def paginate(
        self,
        pager: Any = None,
        *,
        page: int | None = None,
        page_size: int | None = None,
        max_page_size: int | None = None,
    ) -> Any:
        """Decorator adding pagination to the endpoint.

        Overrides flask-smorest's paginate to allow compatibility with
        argument schemas that already include pagination parameters.
        Allows defining multiple @bp.arguments decorators without conflict.

        If pager is None (default), we assume manual handling compatible with
        filter schemas.
        """
        # If a pager class/instance is provided, use standard behavior
        if pager is not None:
            return super().paginate(pager, page=page, page_size=page_size, max_page_size=max_page_size)  # type: ignore

        # Custom behavior for pager=None (manual pagination handling)
        def decorator(func: Any) -> Any:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Try to get params from validated 'filters' dict
                filters = kwargs.get("filters")

                # If not in kwargs, check args (MethodView: args[0]=self, args[1]=filters)
                if filters is None and len(args) > 1:
                    filters = args[1]

                # Fallback to empty dict if not found
                if filters is None:
                    filters = {}

                # Extract values with fallbacks
                p_val = filters.get("page") or page or 1
                p_size_val = filters.get("page_size") or page_size or 10

                # Create parameters object
                pagination_parameters = PaginationParameters(page=p_val, page_size=p_size_val)

                # Inject into kwargs
                kwargs["pagination_parameters"] = pagination_parameters

                # Remove from filters so application logic doesn't see them as filters
                if "page" in filters:
                    del filters["page"]
                if "page_size" in filters:
                    del filters["page_size"]

                # Execute decorated function
                result = func(*args, **kwargs)

                # Handle response (could be value or tuple)
                status = 200
                headers = {}
                if isinstance(result, tuple):
                    n = len(result)
                    if n == 3:
                        result, status, headers = result
                    elif n == 2:
                        result, status = result

                # Set pagination metadata
                if getattr(self, "PAGINATION_HEADER_NAME", None) is not None:
                    result, headers = self._set_pagination_metadata(  # type: ignore
                        pagination_parameters, result, headers
                    )

                return result, status, headers

            return wrapper

        return decorator
