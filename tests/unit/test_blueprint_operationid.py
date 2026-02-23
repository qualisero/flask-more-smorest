"""Unit tests for BlueprintOperationIdMixin.

All tests that verify the generated operationId value use the full OpenAPI
spec (via ``Api + api.spec.to_dict()``) rather than inspecting ``_apidoc``
directly.  This matches the architecture of the new ``_store_endpoint_docs``
implementation where operationIds land in ``blueprint._docs``, not on the
decorated function itself.
"""

from http import HTTPStatus
from typing import Any

from flask import Flask
from flask.views import MethodView
from flask_smorest import Api
from marshmallow import Schema, fields

from flask_more_smorest.crud.blueprint_operationid import (
    HTTP_METHOD_OPERATION_MAP,
    BlueprintOperationIdMixin,
    strip_suffixes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app() -> Flask:
    """Return a minimal Flask app configured for flask-smorest."""
    app = Flask(__name__)
    app.config.update(
        {
            "API_TITLE": "Test",
            "API_VERSION": "v1",
            "OPENAPI_VERSION": "3.0.2",
        }
    )
    return app


def get_op_id(bp: BlueprintOperationIdMixin, path: str, method: str = "get") -> str:
    """Register *bp* and extract the operationId from the compiled spec.

    Args:
        bp: Blueprint to register.
        path: Full path including ``url_prefix`` (e.g. ``"/api/users/"``).
        method: Lowercase HTTP method.
    """
    app = make_app()
    api = Api(app)
    api.register_blueprint(bp)
    spec = api.spec.to_dict()
    return spec["paths"][path][method]["operationId"]


def make_bp(name: str = "test", url_prefix: str = "/api") -> BlueprintOperationIdMixin:
    """Create a fresh blueprint bound to a new Flask app context."""
    return BlueprintOperationIdMixin(name, __name__, url_prefix=url_prefix)


# ---------------------------------------------------------------------------
# Structural / meta tests
# ---------------------------------------------------------------------------


class TestBlueprintMetadata:
    """Basic structural checks."""

    def test_inherits_from_flask_smorest_blueprint(self) -> None:
        from flask_smorest import Blueprint

        assert issubclass(BlueprintOperationIdMixin, Blueprint)

    def test_route_method_is_callable(self) -> None:
        app = Flask(__name__)
        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)
            assert callable(bp.route)

    def test_http_method_map_contains_expected_verbs(self) -> None:
        assert HTTP_METHOD_OPERATION_MAP["get"] == "get"
        assert HTTP_METHOD_OPERATION_MAP["post"] == "create"
        assert HTTP_METHOD_OPERATION_MAP["patch"] == "update"
        assert HTTP_METHOD_OPERATION_MAP["delete"] == "delete"
        assert HTTP_METHOD_OPERATION_MAP["put"] == "set"


# ---------------------------------------------------------------------------
# strip_suffixes() unit tests
# ---------------------------------------------------------------------------


class TestStripSuffixes:
    """Tests for the strip_suffixes() utility function."""

    def test_strip_view(self) -> None:
        assert strip_suffixes("FeeEstimationView") == "FeeEstimation"

    def test_strip_methodview(self) -> None:
        assert strip_suffixes("ValuationMethodView") == "Valuation"

    def test_strip_index(self) -> None:
        assert strip_suffixes("AccreditationIndex") == "Accreditation"

    def test_strip_list(self) -> None:
        assert strip_suffixes("UserList") == "User"

    def test_strip_collection(self) -> None:
        assert strip_suffixes("UserAccreditationCollection") == "UserAccreditation"

    def test_strip_v2(self) -> None:
        assert strip_suffixes("UserAccreditationV2") == "UserAccreditation"

    def test_strip_v1(self) -> None:
        assert strip_suffixes("ExpertListV1") == "Expert"

    def test_strip_compound_view_then_list(self) -> None:
        """UserListView → first 'View' stripped → 'UserList' → then 'List' stripped → 'User'."""
        assert strip_suffixes("UserListView") == "User"

    def test_strip_compound_index_v2(self) -> None:
        """AccreditationIndexV2 → 'V2' stripped → 'AccreditationIndex' → 'Index' stripped → 'Accreditation'."""
        assert strip_suffixes("AccreditationIndexV2") == "Accreditation"

    def test_no_matching_suffix_preserved(self) -> None:
        assert strip_suffixes("UserFull") == "UserFull"
        assert strip_suffixes("UserBasic") == "UserBasic"
        assert strip_suffixes("UserDetails") == "UserDetails"

    def test_name_equal_to_suffix_not_stripped(self) -> None:
        """A name that IS the suffix (e.g. 'View') must not be reduced to ''."""
        assert strip_suffixes("View") == "View"
        assert strip_suffixes("List") == "List"


# ---------------------------------------------------------------------------
# MethodView operationId generation — spec-level assertions
# ---------------------------------------------------------------------------


class TestMethodViewOperationIds:
    """Tests for MethodView-based routes using full spec assertions."""

    def test_list_endpoint_with_trailing_slash(self) -> None:
        """GET / with trailing slash → listProducts (pluralised)."""
        with make_app().app_context():
            bp = make_bp("products")

            @bp.route("/products/")
            class Product(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"products": []}

            assert get_op_id(bp, "/api/products/") == "listProducts"

    def test_list_endpoint_already_plural_class(self) -> None:
        """Already-plural class name → stays plural in list operationId."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items/")
            class Items(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"items": []}

            assert get_op_id(bp, "/api/items/") == "listItems"

    def test_get_single_item(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/product/<int:product_id>")
            class Product(MethodView):
                def get(self, product_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/product/{product_id}") == "getProduct"

    def test_post_endpoint(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/products/")
            class Product(MethodView):
                def post(self) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/products/", method="post") == "createProduct"

    def test_patch_endpoint(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/product/<int:product_id>", methods=["PATCH"])
            class Product(MethodView):
                def patch(self, product_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/product/{product_id}", method="patch") == "updateProduct"

    def test_delete_endpoint(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/product/<int:product_id>", methods=["DELETE"])
            class Product(MethodView):
                def delete(self, product_id: int) -> tuple[str, int]:
                    return "", 204

            assert get_op_id(bp, "/api/product/{product_id}", method="delete") == "deleteProduct"

    def test_put_maps_to_set(self) -> None:
        """PUT uses 'set' prefix (was 'replace' in previous versions)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/request/<int:id>/expert", methods=["PUT"])
            class RequestExpert(MethodView):
                def put(self, id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/request/{id}/expert", method="put") == "setRequestExpert"

    def test_camel_case_class_name(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/product-review/<int:review_id>")
            class ProductReview(MethodView):
                def get(self, review_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/product-review/{review_id}") == "getProductReview"

    def test_manual_doc_operationid_not_overridden(self) -> None:
        """@bp.doc(operationId=...) takes priority over auto-generation."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/product/<int:product_id>")
            class Product(MethodView):
                @bp.doc(operationId="customGetProduct")
                def get(self, product_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/product/{product_id}") == "customGetProduct"


# ---------------------------------------------------------------------------
# strip_suffixes applied to MethodView class names
# ---------------------------------------------------------------------------


class TestSuffixStrippingInOperationIds:
    """Verify strip_suffixes affects the generated operationId."""

    def test_view_suffix_stripped(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/estimate")
            class FeeEstimationView(MethodView):
                def get(self) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/estimate") == "getFeeEstimation"

    def test_v2_suffix_stripped(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/accred/<int:id>")
            class UserAccreditationV2(MethodView):
                def get(self, id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/accred/{id}") == "getUserAccreditation"

    def test_list_suffix_stripped_on_collection(self) -> None:
        """UserList on /users/ → strip 'List' → User → listUsers."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/")
            class UserList(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/users/") == "listUsers"

    def test_compound_suffix_stripped(self) -> None:
        """AccreditationIndexV2 → 'V2' then 'Index' stripped → Accreditation."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/accred/<int:user_id>/<int:accred_id>")
            class AccreditationIndexV2(MethodView):
                def get(self, user_id: int, accred_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/accred/{user_id}/{accred_id}") == "getAccreditation"

    def test_list_view_compound_suffix(self) -> None:
        """UserListView → 'View' then 'List' stripped → User."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/user/<int:id>")
            class UserListView(MethodView):
                def get(self, id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/user/{id}") == "getUser"

    def test_post_with_stripped_suffix(self) -> None:
        """POST on a class with Index suffix → createXxx (not createXxxIndex)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/")
            class UserIndex(MethodView):
                def post(self) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/users/", method="post") == "createUser"


# ---------------------------------------------------------------------------
# Pluralisation tests
# ---------------------------------------------------------------------------


class TestPluralisation:
    """Tests for the _pluralise() method via generated operationIds."""

    def test_singular_class_pluralised(self) -> None:
        """User → Users → listUsers."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/")
            class User(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/users/") == "listUsers"

    def test_already_plural_unchanged(self) -> None:
        """Items is already plural → listItems (not listItemss)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items/")
            class Items(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/items/") == "listItems"

    def test_invariant_plural_unchanged(self) -> None:
        """News is invariant plural → listNews."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/news/")
            class News(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/news/") == "listNews"

    def test_foobybar_compound_pluralisation(self) -> None:
        """AppointmentByRef → AppointmentsByRef (only prefix part pluralised)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/appt/")
            class AppointmentByRef(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/appt/") == "listAppointmentsByRef"

    def test_compound_name_pluralised(self) -> None:
        """ProjectList (after stripping 'List' → 'Project') → listProjects."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/projects/")
            class ProjectList(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/projects/") == "listProjects"

    def test_non_get_method_not_pluralised(self) -> None:
        """POST on a collection does NOT pluralise the name."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items/")
            class Item(MethodView):
                def post(self) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/items/", method="post") == "createItem"


# ---------------------------------------------------------------------------
# Collection detection: many=True from response schema
# ---------------------------------------------------------------------------


class TestManyTrueDetection:
    """Verify that many=True on response schema triggers list operationId."""

    def test_many_true_without_trailing_slash(self) -> None:
        """No trailing slash but many=True on response → listXxx."""

        class ItemSchema(Schema):
            name = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items")
            class Item(MethodView):
                @bp.response(HTTPStatus.OK, ItemSchema(many=True))
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/items") == "listItems"

    def test_many_true_with_trailing_slash(self) -> None:
        """Trailing slash takes precedence; many=True is additive confirmation."""

        class UserSchema(Schema):
            name = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/")
            class User(MethodView):
                @bp.response(HTTPStatus.OK, UserSchema(many=True))
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/users/") == "listUsers"

    def test_many_false_without_trailing_slash_gives_get(self) -> None:
        """many=False (scalar schema) + no trailing slash → getXxx."""

        class UserSchema(Schema):
            name = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/user/<int:id>")
            class User(MethodView):
                @bp.response(HTTPStatus.OK, UserSchema())
                def get(self, id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/user/{id}") == "getUser"

    def test_many_true_does_not_affect_non_get(self) -> None:
        """many=True on a POST response does not make it a 'list' operation."""

        class ItemSchema(Schema):
            name = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items/", methods=["POST"])
            class Item(MethodView):
                @bp.response(HTTPStatus.CREATED, ItemSchema(many=True))
                def post(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/items/", method="post") == "createItem"


# ---------------------------------------------------------------------------
# Collection detection: trailing slash heuristic
# ---------------------------------------------------------------------------


class TestCollectionDetectionHeuristic:
    """Tests focused on the trailing-slash heuristic for collection endpoints."""

    def test_trailing_slash_at_root(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/")
            class Item(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/") == "listItems"

    def test_no_trailing_slash_gives_get(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items")
            class Item(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/items") == "getItem"

    def test_path_param_no_trailing_slash(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/<int:user_id>")
            class Users(MethodView):
                def get(self, user_id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/users/{user_id}") == "getUsers"

    def test_non_get_on_trailing_slash_path(self) -> None:
        """Trailing slash does not affect non-GET method (should still be createXxx)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/items/")
            class Item(MethodView):
                def post(self) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/items/", method="post") == "createItem"


# ---------------------------------------------------------------------------
# Function-based routes
# ---------------------------------------------------------------------------


class TestFunctionRoutes:
    """Tests for function-based (non-MethodView) routes."""

    def test_auto_generated_from_function_name(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/custom")
            def custom_endpoint() -> dict[str, str]:
                return {"message": "ok"}

            assert get_op_id(bp, "/api/custom") == "customEndpoint"

    def test_explicit_operation_id(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/special", operation_id="getSpecialThing")
            def my_func() -> dict[str, Any]:
                return {}

            assert get_op_id(bp, "/api/special") == "getSpecialThing"

    def test_explicit_operation_id_with_methods(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/action", methods=["PUT"], operation_id="_deprecated_doAction")
            def action() -> dict[str, Any]:
                return {}

            assert get_op_id(bp, "/api/action", method="put") == "_deprecated_doAction"

    def test_with_response_decorator(self) -> None:
        class ResponseSchema(Schema):
            message = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/with_response", methods=["GET"])
            @bp.response(HTTPStatus.OK, ResponseSchema)
            def endpoint_with_response() -> dict[str, str]:
                return {"message": "ok"}

            assert get_op_id(bp, "/api/with_response") == "endpointWithResponse"

    def test_with_arguments_decorator(self) -> None:
        class ArgsSchema(Schema):
            name = fields.Str(required=True)

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/with_args", methods=["POST"])
            @bp.arguments(ArgsSchema)
            def endpoint_with_args(args: dict[str, Any]) -> dict[str, str]:
                return {"message": "ok"}

            assert get_op_id(bp, "/api/with_args", method="post") == "endpointWithArgs"

    def test_with_multiple_decorators(self) -> None:
        class InputSchema(Schema):
            username = fields.Str(required=True)

        class OutputSchema(Schema):
            token = fields.Str()

        with make_app().app_context():
            bp = make_bp()

            @bp.route("/complex", methods=["POST"])
            @bp.arguments(InputSchema)
            @bp.response(HTTPStatus.OK, OutputSchema)
            def complex_endpoint(args: dict[str, Any]) -> dict[str, str]:
                return {"token": "abc"}

            assert get_op_id(bp, "/api/complex", method="post") == "complexEndpoint"

    def test_multiple_routes_different_operation_ids(self) -> None:
        """Two routes on same function: one auto-generated, one explicit."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/action", methods=["PUT"])
            @bp.route(
                "/status",
                methods=["PUT"],
                operation_id="_deprecated_requestValuationAction",
            )
            def test_func() -> dict[str, Any]:
                return {}

            app = make_app()
            api = Api(app)
            api.register_blueprint(bp)
            spec = api.spec.to_dict()

            assert spec["paths"]["/api/action"]["put"]["operationId"] == "testFunc"
            assert spec["paths"]["/api/status"]["put"]["operationId"] == "_deprecated_requestValuationAction"


# ---------------------------------------------------------------------------
# operation_id_prefix and operation_id_suffix
# ---------------------------------------------------------------------------


class TestOperationIdPrefixSuffix:
    """Tests for operation_id_prefix and operation_id_suffix on route()."""

    def test_prefix_applied_to_all_methods(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/current", methods=["GET", "PATCH"])
            @bp.route("/legacy", methods=["GET", "PATCH"], operation_id_prefix="_deprecated_")
            class ErsView(MethodView):
                def get(self) -> dict[str, Any]:
                    return {}

                def patch(self) -> dict[str, Any]:
                    return {}

            app = make_app()
            api = Api(app)
            api.register_blueprint(bp)
            spec = api.spec.to_dict()

            assert spec["paths"]["/api/current"]["get"]["operationId"] == "getErs"
            assert spec["paths"]["/api/current"]["patch"]["operationId"] == "updateErs"
            assert spec["paths"]["/api/legacy"]["get"]["operationId"] == "_deprecated_getErs"
            assert spec["paths"]["/api/legacy"]["patch"]["operationId"] == "_deprecated_updateErs"

    def test_suffix_applied_to_all_methods(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/v1", methods=["GET", "PATCH"])
            @bp.route("/v2", methods=["GET", "PATCH"], operation_id_suffix="_v2")
            class ErsView(MethodView):
                def get(self) -> dict[str, Any]:
                    return {}

                def patch(self) -> dict[str, Any]:
                    return {}

            app = make_app()
            api = Api(app)
            api.register_blueprint(bp)
            spec = api.spec.to_dict()

            assert spec["paths"]["/api/v1"]["get"]["operationId"] == "getErs"
            assert spec["paths"]["/api/v1"]["patch"]["operationId"] == "updateErs"
            assert spec["paths"]["/api/v2"]["get"]["operationId"] == "getErs_v2"
            assert spec["paths"]["/api/v2"]["patch"]["operationId"] == "updateErs_v2"

    def test_prefix_and_suffix_combined(self) -> None:
        with make_app().app_context():
            bp = make_bp()

            @bp.route(
                "/old",
                methods=["GET", "POST"],
                operation_id_prefix="_deprecated_",
                operation_id_suffix="_v1",
            )
            class UserView(MethodView):
                def get(self) -> dict[str, Any]:
                    return {}

                def post(self) -> dict[str, Any]:
                    return {}

            app = make_app()
            api = Api(app)
            api.register_blueprint(bp)
            spec = api.spec.to_dict()

            assert spec["paths"]["/api/old"]["get"]["operationId"] == "_deprecated_getUser_v1"
            assert spec["paths"]["/api/old"]["post"]["operationId"] == "_deprecated_createUser_v1"

    def test_prefix_on_collection_endpoint(self) -> None:
        """Prefix is applied after the full base_id is generated (list + plural)."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/users/", methods=["GET"], operation_id_prefix="v2_")
            class User(MethodView):
                def get(self) -> list[Any]:
                    return []

            assert get_op_id(bp, "/api/users/") == "v2_listUsers"

    def test_manual_doc_wins_over_prefix(self) -> None:
        """Manual @bp.doc(operationId=...) is not overridden by operation_id_prefix."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/user/<int:id>", operation_id_prefix="_dep_")
            class UserView(MethodView):
                @bp.doc(operationId="myManualId")
                def get(self, id: int) -> dict[str, Any]:
                    return {}

            assert get_op_id(bp, "/api/user/{id}") == "myManualId"

    def test_prefix_does_not_affect_routes_without_it(self) -> None:
        """A prefix on one route of a MethodView does not leak to other routes."""
        with make_app().app_context():
            bp = make_bp()

            @bp.route("/new")
            @bp.route("/old", operation_id_prefix="legacy_")
            class ItemView(MethodView):
                def get(self) -> dict[str, Any]:
                    return {}

            app = make_app()
            api = Api(app)
            api.register_blueprint(bp)
            spec = api.spec.to_dict()

            assert spec["paths"]["/api/new"]["get"]["operationId"] == "getItem"
            assert spec["paths"]["/api/old"]["get"]["operationId"] == "legacy_getItem"
