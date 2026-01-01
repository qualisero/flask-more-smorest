"""Unit tests for BlueprintOperationIdMixin."""

from flask.views import MethodView

from flask_more_smorest.blueprint_operationid import HTTP_METHOD_OPERATION_MAP, BlueprintOperationIdMixin


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
            bp = BlueprintOperationIdMixin("users", __name__)

            # Define a MethodView class
            @bp.route("/")
            class Users(MethodView):
                methods = ["GET"]

                def get(self) -> dict:
                    return {"users": []}

            # Check that operationId was set
            get_method = getattr(Users, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "listUser"

    def test_operation_id_generation_handles_plural_class_names(self) -> None:
        """Plural MethodView class names should drop the trailing 's'."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("companies", __name__)

            @bp.route("/")
            class Companies(MethodView):
                methods = ["GET"]

                def get(self) -> dict:
                    return {"companies": []}

            get_method = getattr(Companies, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert apidoc["manual_doc"]["operationId"] == "listCompanie"

    def test_operation_id_generation_for_get_endpoint(self) -> None:
        """Test operationId generation for GET single item endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["GET"]

                def get(self, user_id: str) -> dict:
                    return {"user": {}}

            get_method = getattr(User, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getUser"

    def test_operation_id_generation_for_post_endpoint(self) -> None:
        """Test operationId generation for POST endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/")
            class Users(MethodView):
                methods = ["POST"]

                def post(self) -> dict:
                    return {"user": {}}

            post_method = getattr(Users, "post")
            apidoc = getattr(post_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "createUsers"

    def test_operation_id_generation_for_patch_endpoint(self) -> None:
        """Test operationId generation for PATCH endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["PATCH"]

                def patch(self, user_id: str) -> dict:
                    return {"user": {}}

            patch_method = getattr(User, "patch")
            apidoc = getattr(patch_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "updateUser"

    def test_operation_id_generation_for_delete_endpoint(self) -> None:
        """Test operationId generation for DELETE endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["DELETE"]

                def delete(self, user_id: str) -> tuple[str, int]:
                    return "", 204

            delete_method = getattr(User, "delete")
            apidoc = getattr(delete_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "deleteUser"

    def test_operation_id_with_snake_case_class_name(self) -> None:
        """Test operationId generation with snake_case class name."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("user_profiles", __name__)

            @bp.route("/<int:user_profile_id>")
            class UserProfile(MethodView):
                methods = ["GET"]

                def get(self, user_profile_id: str) -> dict:
                    return {"profile": {}}

            get_method = getattr(UserProfile, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getUserProfile"

    def test_manual_operation_id_not_overridden(self) -> None:
        """Test that manually set operationId is not overridden."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["GET"]

                @bp.doc(operationId="customGetUser")
                def get(self, user_id: str) -> dict:
                    return {"user": {}}

            get_method = getattr(User, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            # Manual operationId should be preserved
            assert apidoc["manual_doc"]["operationId"] == "customGetUser"

    def test_operation_id_for_function_route(self) -> None:
        """Test operationId generation for function-based routes."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/custom")
            def custom_endpoint() -> dict:
                return {"message": "success"}

            # For function-based routes, use function name
            apidoc = getattr(custom_endpoint, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "customEndpoint"
