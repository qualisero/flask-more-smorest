"""Enhanced Blueprint with automatic operationId generation.

This module provides BlueprintOperationIdMixin that extends Flask-Smorest's
Blueprint to automatically generate OpenAPI operationId values for endpoints.
"""

from collections.abc import Callable
from typing import Any, Final, cast

import inflect
from flask.views import MethodView
from flask_smorest import Blueprint

from ..utils import convert_snake_to_camel

inflector = inflect.engine()


def strip_suffixes(name: str) -> str:
    """Strip common boilerplate suffixes from class or function names.

    Strips suffixes in priority order so compound suffixes like ``V2List``
    are handled correctly (``V2`` removed first, then ``List``).

    Args:
        name: Class or function name to normalise.

    Returns:
        Name with recognised suffixes removed.

    Example:
        >>> strip_suffixes("UserListView")
        'User'
        >>> strip_suffixes("AccreditationIndexV2")
        'Accreditation'
        >>> strip_suffixes("FeeEstimationView")
        'FeeEstimation'
    """
    # Order matters — strip version tags before structural tags
    suffixes = [
        "V2",
        "_v2",
        "V1",
        "_v1",
        "MethodView",
        "View",
        "Index",
        "List",
        "Collection",
    ]
    for suffix in suffixes:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
    return name


HTTP_METHOD_OPERATION_MAP: Final[dict[str, str]] = {
    "patch": "update",
    "delete": "delete",
    "get": "get",
    "post": "create",
    "put": "set",
}


class BlueprintOperationIdMixin(Blueprint):
    """Blueprint mixin that provides automatic operationId generation.

    Extends Flask-Smorest's Blueprint to automatically generate OpenAPI
    ``operationId`` values for routes based on the route pattern, HTTP method,
    class name (after suffix stripping) and response schema.

    **Collection detection** for GET requests (in priority order):

    1. Manual ``@bp.doc(operationId=…)`` override → used as-is.
    2. Explicit ``operation_id=`` kwarg on ``route()`` → used as-is.
    3. Trailing slash in path → collection (``listXxx``).
    4. ``many=True`` on response schema → collection (``listXxx``).
    5. Default → individual (``getXxx``).

    Examples::

        bp = BlueprintOperationIdMixin('users', __name__)

        # Auto-generated: listUsers
        @bp.route('/users/')
        class User(MethodView):
            def get(self): ...

        # Custom full operationId for a function-based route
        @bp.route('/special', operation_id='getSpecialUsers')
        def special_users(): ...

        # Prefix for all methods on a MethodView (e.g. deprecation)
        @bp.route('/legacy', operation_id_prefix='_deprecated_')
        class Item(MethodView):
            def get(self): ...   # → _deprecated_getItem
            def post(self): ...  # → _deprecated_createItem

        # Suffix for versioning
        @bp.route('/v2/users/', operation_id_suffix='_v2')
        class User(MethodView):
            def get(self): ...   # → listUsers_v2

        # Combine prefix and suffix
        @bp.route('/old', operation_id_prefix='legacy_', operation_id_suffix='_v1')
        class OldEndpoint(MethodView):
            def get(self): ...   # → legacy_getOldEndpoint_v1
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Keyed by (rule, methods_tuple) → full custom operationId
        self._route_operation_ids: dict[tuple[str, tuple[str, ...]], str] = {}
        # Keyed by (rule, methods_tuple) → prefix string
        self._route_operation_id_prefixes: dict[tuple[str, tuple[str, ...]], str] = {}
        # Keyed by (rule, methods_tuple) → suffix string
        self._route_operation_id_suffixes: dict[tuple[str, tuple[str, ...]], str] = {}
        # Keyed by (rule, id(view_func)) → (methods, prefix_or_custom, suffix, is_full_op_id)
        self._pending_route_info: dict[
            tuple[str, int],
            tuple[tuple[str, ...], str | None, str | None, bool],
        ] = {}
        self._current_rule: str | None = None

    def route(
        self,
        rule: str,
        *,
        operation_id: str | None = None,
        operation_id_prefix: str | None = None,
        operation_id_suffix: str | None = None,
        parameters: list | None = None,
        tags: list[str] | None = None,
        **options: Any,
    ) -> Callable[[type["MethodView"] | Callable], type["MethodView"] | Callable]:
        """Override route() to capture operationId customisation options.

        Args:
            rule: URL rule for the route.
            operation_id: Explicit full operationId (function-based routes) or
                override for every method on a MethodView.
            operation_id_prefix: Prefix prepended to the auto-generated
                operationId for every method on a MethodView.
            operation_id_suffix: Suffix appended to the auto-generated
                operationId for every method on a MethodView.
            parameters: OpenAPI path-level parameters (passed to parent).
            tags: OpenAPI tags (passed to parent).
            **options: Additional Flask routing options.

        Returns:
            Decorator for the view class or function.
        """
        methods: tuple[str, ...] = tuple(sorted(options.get("methods", ["GET"]))) if options.get("methods") else ()
        route_key = (rule, methods)

        if operation_id is not None:
            self._route_operation_ids[route_key] = operation_id
        if operation_id_prefix is not None:
            self._route_operation_id_prefixes[route_key] = operation_id_prefix
        if operation_id_suffix is not None:
            self._route_operation_id_suffixes[route_key] = operation_id_suffix

        return cast(
            Callable[[type["MethodView"] | Callable], type["MethodView"] | Callable],
            super().route(rule, parameters=parameters, tags=tags, **options),
        )

    def add_url_rule(
        self,
        rule: str,
        endpoint: str | None = None,
        view_func: Callable | None = None,
        provide_automatic_options: bool | None = None,
        *,
        parameters: list | None = None,
        tags: list[str] | None = None,
        **options: Any,
    ) -> None:
        """Override to capture per-route operationId metadata before parent stores docs."""
        methods: tuple[str, ...] = tuple(sorted(options.get("methods", ("GET",))))
        route_key = (rule, methods)

        # Fall back to the empty-methods key because route() stores () when no
        # explicit methods kwarg is given (e.g. a plain function-based GET route).
        custom_op_id = self._route_operation_ids.get(route_key) or self._route_operation_ids.get((rule, ()))
        prefix = self._route_operation_id_prefixes.get(route_key) or self._route_operation_id_prefixes.get((rule, ()))
        suffix = self._route_operation_id_suffixes.get(route_key) or self._route_operation_id_suffixes.get((rule, ()))

        if view_func is not None:
            pending_key = (rule, id(view_func))
            self._pending_route_info[pending_key] = (
                methods,
                custom_op_id if custom_op_id is not None else prefix,
                suffix,
                custom_op_id is not None,
            )
            self._current_rule = rule

        super().add_url_rule(
            rule,
            endpoint,
            view_func,
            provide_automatic_options,
            parameters=parameters,
            tags=tags,
            **options,
        )

    def _store_endpoint_docs(
        self,
        endpoint: str,
        obj: type["MethodView"] | Callable,
        parameters: Any,
        tags: Any,
        **options: Any,
    ) -> None:
        """Override to inject operationId into stored docs after all decorators are applied.

        Parent calls this to persist decorator metadata.  We retrieve the
        previously stored customisation options and inject the operationId for
        each HTTP method that does not already carry a manual override.
        """
        super()._store_endpoint_docs(endpoint, obj, parameters, tags, **options)

        rule = self._current_rule
        if rule is None:
            return

        pending_key = (rule, id(obj))
        route_info = self._pending_route_info.pop(pending_key, None)
        if route_info is None:
            return

        _methods, prefix_or_custom, suffix, is_full_op_id = route_info
        endpoint_doc_info = self._docs.get(endpoint, {})

        for method_lower, doc in endpoint_doc_info.items():
            if method_lower == "parameters" or not isinstance(doc, dict):
                continue

            # Respect an existing manual operationId set by @bp.doc(operationId=...)
            if doc.get("manual_doc", {}).get("operationId"):
                continue

            if is_full_op_id:
                # Explicit full operationId supplied via route(operation_id=...)
                doc.setdefault("manual_doc", {})["operationId"] = prefix_or_custom
                continue

            # Detect collection for GET via many=True on response schema
            many = self._extract_many_from_response(doc) if method_lower == "get" else None

            op_id = self._generate_operation_id_for_method(obj, method_lower, rule, prefix_or_custom, suffix, many)
            doc.setdefault("manual_doc", {})["operationId"] = op_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_many_from_response(self, doc: dict[str, Any]) -> bool:
        """Return True when the stored response schema carries ``many=True``.

        Inspects the ``response`` metadata stored by Flask-Smorest's
        ``@bp.response()`` decorator.  Returns ``False`` if no schema is found
        or the attribute is absent.
        """
        responses = doc.get("response", {}).get("responses", {})
        for status_code in (200, 201, "200", "201"):
            entry = responses.get(status_code)
            if entry:
                schema = entry[0].get("schema")
                if schema is not None and hasattr(schema, "many"):
                    return bool(schema.many)
        return False

    def _is_collection_endpoint(
        self,
        method_name: str,
        rule: str,
        many: bool | None = None,
    ) -> bool:
        """Return True when a GET endpoint represents a collection.

        Priority:

        1. Trailing slash → collection.
        2. ``many=True`` on response schema → collection.
        3. Otherwise → individual.

        Args:
            method_name: Lowercase HTTP method name.
            rule: URL route pattern.
            many: Whether the response schema has ``many=True``.
        """
        if method_name != "get":
            return False
        if rule.endswith("/"):
            return True
        return many is True

    def _pluralise(self, name: str) -> str:
        """Return a pluralised version of *name* using the ``inflect`` engine.

        Handles:

        * Already-plural words (e.g. ``News`` → ``News``).
        * Compound ``FooByBar`` form: only the prefix is pluralised
          (``AppointmentByRef`` → ``AppointmentsByRef``).

        Args:
            name: Singular (or already-plural) class name without suffixes.
        """
        # Handle FooByBar compound form
        parts = name.split("By")
        if len(parts) > 1 and parts[1] and parts[1][0].isupper():
            return f"{self._pluralise(parts[0])}By{parts[1]}"

        # If inflect considers it already plural, keep it
        if inflector.singular_noun(name) is False:
            plural_form = inflector.plural_noun(name)
            name = str(plural_form) if plural_form else name
        return name

    def _generate_operation_id_for_method(
        self,
        obj: type["MethodView"] | Callable,
        method_name: str,
        rule: str,
        prefix_or_custom: str | None,
        suffix: str | None = None,
        many: bool | None = None,
    ) -> str:
        """Build the final operationId string for one HTTP method.

        Args:
            obj: The MethodView subclass or function being decorated.
            method_name: Lowercase HTTP method (e.g. ``"get"``).
            rule: URL route pattern (used for trailing-slash detection).
            prefix_or_custom: Prefix string for MethodView; full ID for functions.
            suffix: Optional suffix to append (MethodView only).
            many: Whether the response schema has ``many=True`` (GET only).
        """
        is_method_view = isinstance(obj, type) and issubclass(obj, MethodView)

        if not is_method_view and prefix_or_custom:
            # Function-based route with an explicit custom operationId
            return prefix_or_custom

        if is_method_view:
            class_name = strip_suffixes(obj.__name__)

            if self._is_collection_endpoint(method_name, rule, many):
                class_name = self._pluralise(class_name)
                operation_id = f"list{class_name}"
            else:
                operation_name = HTTP_METHOD_OPERATION_MAP.get(method_name, method_name)
                operation_id = f"{operation_name}{class_name}"
        else:
            # Function-based route: use function name after suffix stripping
            operation_id = strip_suffixes(obj.__name__)

        camel = convert_snake_to_camel(operation_id)
        # Ensure camelCase (lowercase first char) regardless of how
        # convert_snake_to_camel renders its output.
        base_id = camel[0].lower() + camel[1:] if camel else camel

        if is_method_view:
            if prefix_or_custom:
                base_id = prefix_or_custom + base_id
            if suffix:
                base_id = base_id + suffix

        return base_id
