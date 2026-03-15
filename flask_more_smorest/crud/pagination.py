from functools import wraps
from typing import Any

from flask_smorest.pagination import PaginationParameters
from werkzeug.exceptions import BadRequest


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

                def _coerce_int(name: str, value: Any, default: int, *, allow_zero: bool = False) -> int:
                    candidate = value if value is not None else default
                    if candidate is None:
                        raise BadRequest(f"Missing pagination parameter: {name}")
                    try:
                        int_value = int(candidate)
                    except (TypeError, ValueError) as exc:
                        raise BadRequest(
                            f"{name} must be a non-negative integer"
                            if allow_zero
                            else f"{name} must be a positive integer"
                        ) from exc
                    min_val = 0 if allow_zero else 1
                    if int_value < min_val:
                        raise BadRequest(
                            f"{name} must be a non-negative integer"
                            if allow_zero
                            else f"{name} must be a positive integer"
                        )
                    return int_value

                # Extract values with fallbacks and validation
                raw_page = filters.get("page")
                if raw_page is None:
                    raw_page = page
                p_val = _coerce_int("page", raw_page, default=1)

                raw_page_size = filters.get("page_size")
                if raw_page_size is None:
                    raw_page_size = page_size
                p_size_default = page_size if page_size is not None else 20
                p_size_val = _coerce_int("page_size", raw_page_size, default=p_size_default, allow_zero=True)

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
                    metadata_parameters = pagination_parameters
                    if (
                        pagination_parameters.page_size == 0
                        and pagination_parameters.item_count is not None
                        and pagination_parameters.item_count > 0
                    ):
                        metadata_parameters = PaginationParameters(
                            page=pagination_parameters.page,
                            page_size=pagination_parameters.item_count,
                        )
                        metadata_parameters.item_count = pagination_parameters.item_count

                    result, headers = self._set_pagination_metadata(  # type: ignore
                        metadata_parameters, result, headers
                    )

                return result, status, headers

            return wrapper

        return decorator
