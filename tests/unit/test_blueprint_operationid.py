"""Unit tests for BlueprintOperationIdMixin."""

# pyright: reportAttributeAccessIssue=false

from typing import Any

from flask.views import MethodView

from flask_more_smorest.crud.blueprint_operationid import (
    HTTP_METHOD_OPERATION_MAP,
    BlueprintOperationIdMixin,
)


class TestBlueprintOperationIdMixin:
    """Tests for BlueprintOperationIdMixin class."""

    def test_mixin_inheritance(self) -> None:
        """Test that BlueprintOperationIdMixin inherits from Blueprint."""
        from flask_smorest import Blueprint

        assert issubclass(BlueprintOperationIdMixin, Blueprint)

    def test_route_method_exists(self) -> None:
        """Test that route method exists and can be called."""
        # Create a minimal mock app
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)
            assert hasattr(bp, "route")
            assert callable(bp.route)

    def test_default_operation_name_map_contains_common_methods(self) -> None:
        """HTTP_METHOD_OPERATION_MAP includes verbs we rely on."""
        assert HTTP_METHOD_OPERATION_MAP["get"] == "get"
        assert HTTP_METHOD_OPERATION_MAP["post"] == "create"
        assert HTTP_METHOD_OPERATION_MAP["patch"] == "update"

    def test_operation_id_generation_for_list_endpoint(self) -> None:
        """Test operationId generation for list endpoints."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            # Define a MethodView class
            @bp.route("/")
            class Products(MethodView):
                methods = ["GET"]

                def get(self) -> dict[str, list[Any]]:
                    return {"products": []}

            # Check that operationId was set
            get_method = Products.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "listProducts"

    def test_operation_id_generation_handles_plural_class_names(self) -> None:
        """Plural MethodView class names should drop the trailing 's'."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("items", __name__)

            @bp.route("/")
            class Items(MethodView):
                methods = ["GET"]

                def get(self) -> dict[str, list[Any]]:
                    return {"items": []}

            get_method = Items.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert apidoc["manual_doc"]["operationId"] == "listItems"

    def test_operation_id_generation_for_get_endpoint(self) -> None:
        """Test operationId generation for GET single item endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            @bp.route("/<int:product_id>")
            class Product(MethodView):
                methods = ["GET"]

                def get(self, product_id: int) -> dict[str, dict[str, Any]]:
                    return {"product": {}}

            get_method = Product.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getProduct"

    def test_operation_id_generation_for_post_endpoint(self) -> None:
        """Test operationId generation for POST endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            @bp.route("/")
            class Products(MethodView):
                methods = ["POST"]

                def post(self) -> dict[str, dict[str, Any]]:
                    return {"product": {}}

            post_method = Products.post  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(post_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "createProducts"

    def test_operation_id_generation_for_patch_endpoint(self) -> None:
        """Test operationId generation for PATCH endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            @bp.route("/<int:product_id>")
            class Product(MethodView):
                methods = ["PATCH"]

                def patch(self, product_id: int) -> dict[str, dict[str, Any]]:
                    return {"product": {}}

            patch_method = Product.patch  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(patch_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "updateProduct"

    def test_operation_id_generation_for_delete_endpoint(self) -> None:
        """Test operationId generation for DELETE endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            @bp.route("/<int:product_id>")
            class Product(MethodView):
                methods = ["DELETE"]

                def delete(self, product_id: int) -> tuple[str, int]:
                    return "", 204

            delete_method = Product.delete  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(delete_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "deleteProduct"

    def test_operation_id_with_snake_case_class_name(self) -> None:
        """Test operationId generation with snake_case class name."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("product_reviews", __name__)

            @bp.route("/<int:review_id>")
            class ProductReview(MethodView):
                methods = ["GET"]

                def get(self, review_id: int) -> dict[str, dict[str, Any]]:
                    return {"review": {}}

            get_method = ProductReview.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getProductReview"

    def test_manual_operation_id_not_overridden(self) -> None:
        """Test that manually set operationId is not overridden."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("products", __name__)

            @bp.route("/<int:product_id>")
            class Product(MethodView):
                methods = ["GET"]

                @bp.doc(operationId="customGetProduct")
                def get(self, product_id: int) -> dict[str, dict[str, Any]]:
                    return {"product": {}}

            get_method = Product.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            # Manual operationId should be preserved
            assert apidoc["manual_doc"]["operationId"] == "customGetProduct"

    def test_operation_id_for_function_route(self) -> None:
        """Test operationId generation for function-based routes."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/custom")
            def custom_endpoint() -> dict[str, str]:
                return {"message": "success"}

            # For function-based routes, use function name
            apidoc = getattr(custom_endpoint, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "customEndpoint"

    def test_operation_id_with_response_decorator(self) -> None:
        """Test operationId generation for function routes with @response decorator.

        This test verifies the fix for the bug where operationId was not being
        generated for function-based routes that used @bp.response() or other
        Flask-Smorest decorators.
        """
        from http import HTTPStatus

        from flask import Flask
        from marshmallow import Schema, fields

        app = Flask(__name__)

        class ResponseSchema(Schema):
            message = fields.Str()

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/with_response", methods=["GET"])
            @bp.response(HTTPStatus.OK, ResponseSchema)
            def endpoint_with_response() -> dict[str, str]:
                return {"message": "success"}

            # operationId should still be generated even with @response decorator
            apidoc = getattr(endpoint_with_response, "_apidoc", {})
            assert "manual_doc" in apidoc, f"Expected 'manual_doc' in _apidoc, got: {apidoc}"
            assert "operationId" in apidoc["manual_doc"], f"Expected 'operationId' in manual_doc, got: {apidoc}"
            assert apidoc["manual_doc"]["operationId"] == "endpointWithResponse"
            # Should also have response info
            assert "response" in apidoc

    def test_operation_id_with_arguments_decorator(self) -> None:
        """Test operationId generation for function routes with @arguments decorator."""
        from flask import Flask
        from marshmallow import Schema, fields

        app = Flask(__name__)

        class ArgsSchema(Schema):
            name = fields.Str(required=True)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/with_args", methods=["POST"])
            @bp.arguments(ArgsSchema)
            def endpoint_with_args(args: dict[str, Any]) -> dict[str, str]:
                return {"message": "success"}

            # operationId should still be generated even with @arguments decorator
            apidoc = getattr(endpoint_with_args, "_apidoc", {})
            assert "manual_doc" in apidoc, f"Expected 'manual_doc' in _apidoc, got: {apidoc}"
            assert "operationId" in apidoc["manual_doc"], f"Expected 'operationId' in manual_doc, got: {apidoc}"
            assert apidoc["manual_doc"]["operationId"] == "endpointWithArgs"
            # Should also have arguments info
            assert "arguments" in apidoc

    def test_operation_id_with_multiple_decorators(self) -> None:
        """Test operationId generation with multiple Flask-Smorest decorators.

        This simulates the real-world scenario in UserBlueprint where endpoints
        like /login/ have both @arguments and @response decorators.
        """
        from http import HTTPStatus

        from flask import Flask
        from marshmallow import Schema, fields

        app = Flask(__name__)

        class InputSchema(Schema):
            username = fields.Str(required=True)

        class OutputSchema(Schema):
            token = fields.Str()

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/complex", methods=["POST"])
            @bp.arguments(InputSchema)
            @bp.response(HTTPStatus.OK, OutputSchema)
            def complex_endpoint(args: dict[str, Any]) -> dict[str, str]:
                return {"token": "abc123"}

            # operationId should be generated with multiple decorators
            apidoc = getattr(complex_endpoint, "_apidoc", {})
            assert "manual_doc" in apidoc, f"Expected 'manual_doc' in _apidoc, got: {apidoc}"
            assert "operationId" in apidoc["manual_doc"], f"Expected 'operationId' in manual_doc, got: {apidoc}"
            assert apidoc["manual_doc"]["operationId"] == "complexEndpoint"
            # Should have both arguments and response info
            assert "arguments" in apidoc
            assert "response" in apidoc


class TestCollectionDetectionLogic:
    """Test improved collection detection logic based on trailing slash."""

    def test_collection_with_singular_class_name(self) -> None:
        """Test that singular class names on collection paths generate list operations.

        This verifies the fix for the TODO comment issue where the old logic
        required both class name ending in 's' AND trailing slash.
        """
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Singular class name on collection path (with trailing slash)
            @bp.route("/users/")
            class User(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"users": []}

            get_method = User.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "listUser" because of trailing slash
            assert apidoc["manual_doc"]["operationId"] == "listUser"

    def test_single_item_with_path_param_no_trailing_slash(self) -> None:
        """Test that paths with params but no trailing slash generate get operations."""
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Single-item path without trailing slash
            @bp.route("/users/<int:user_id>")
            class Users(MethodView):
                def get(self, user_id: int) -> dict[str, dict[str, Any]]:
                    return {"user": {}}

            get_method = Users.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "getUsers" because no trailing slash
            assert apidoc["manual_doc"]["operationId"] == "getUsers"

    def test_collection_without_trailing_slash(self) -> None:
        """Test that collection paths without trailing slash generate get operations.

        Note: Without trailing slash, we cannot distinguish collection from single item,
        so we default to 'get' operation.
        """
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Collection path without trailing slash
            @bp.route("/items")
            class Item(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"items": []}

            get_method = Item.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "getItem" because no trailing slash
            assert apidoc["manual_doc"]["operationId"] == "getItem"

    def test_collection_with_already_plural_name(self) -> None:
        """Test class names that are already plural (News, Series, etc.)."""
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Already plural name on collection path
            @bp.route("/news/")
            class News(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"news": []}

            get_method = News.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "listNews" because of trailing slash
            assert apidoc["manual_doc"]["operationId"] == "listNews"

    def test_single_item_with_trailing_slash(self) -> None:
        """Test that paths with params and trailing slash generate list operations.

        Note: Trailing slash takes precedence, so even with path params,
        we generate 'list' operation. This is a trade-off of the simpler heuristic.
        """
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Single-item path with trailing slash
            @bp.route("/products/<string:product_id>/")
            class Product(MethodView):
                def get(self, product_id: str) -> dict[str, dict[str, Any]]:
                    return {"product": {}}

            get_method = Product.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "listProduct" because of trailing slash (even with path param)
            assert apidoc["manual_doc"]["operationId"] == "listProduct"

    def test_collection_at_root_path(self) -> None:
        """Test collection operations at root path."""
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            # Root path (ends with /)
            @bp.route("/")
            class Item(MethodView):
                def get(self) -> dict[str, list[Any]]:
                    return {"items": []}

            get_method = Item.get  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "listItem" because ends with /
            assert apidoc["manual_doc"]["operationId"] == "listItem"

    def test_non_get_methods_not_affected(self) -> None:
        """Test that non-GET methods don't use collection logic."""
        from flask import Flask
        from flask.views import MethodView

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/items/")
            class Item(MethodView):
                def post(self) -> dict[str, dict[str, Any]]:
                    return {"item": {}}

            post_method = Item.post  # type: ignore[reportFunctionMemberAccess]
            apidoc = getattr(post_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            # Should be "createItem" not "listItem"
            assert apidoc["manual_doc"]["operationId"] == "createItem"
