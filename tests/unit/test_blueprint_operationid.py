"""Unit tests for BlueprintOperationIdMixin."""

from flask.views import MethodView

from flask_more_smorest.blueprint_operationid import BlueprintOperationIdMixin


class TestBlueprintOperationIdMixin:
    """Tests for BlueprintOperationIdMixin class."""

    def test_mixin_inheritance(self):
        """Test that BlueprintOperationIdMixin inherits from Blueprint."""
        from flask_smorest import Blueprint

        assert issubclass(BlueprintOperationIdMixin, Blueprint)

    def test_route_method_exists(self):
        """Test that route method exists and can be called."""
        # Create a minimal mock app
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)
            assert hasattr(bp, "route")
            assert callable(bp.route)

    def test_operation_id_generation_for_list_endpoint(self):
        """Test operationId generation for list endpoints."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            # Define a MethodView class
            @bp.route("/")
            class Users(MethodView):
                methods = ["GET"]

                def get(self):
                    return {"users": []}

            # Check that operationId was set
            get_method = getattr(Users, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "listUser"

    def test_operation_id_generation_for_get_endpoint(self):
        """Test operationId generation for GET single item endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["GET"]

                def get(self, user_id):
                    return {"user": {}}

            get_method = getattr(User, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getUser"

    def test_operation_id_generation_for_post_endpoint(self):
        """Test operationId generation for POST endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/")
            class Users(MethodView):
                methods = ["POST"]

                def post(self):
                    return {"user": {}}

            post_method = getattr(Users, "post")
            apidoc = getattr(post_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "createUsers"

    def test_operation_id_generation_for_patch_endpoint(self):
        """Test operationId generation for PATCH endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["PATCH"]

                def patch(self, user_id):
                    return {"user": {}}

            patch_method = getattr(User, "patch")
            apidoc = getattr(patch_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "updateUser"

    def test_operation_id_generation_for_delete_endpoint(self):
        """Test operationId generation for DELETE endpoint."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["DELETE"]

                def delete(self, user_id):
                    return "", 204

            delete_method = getattr(User, "delete")
            apidoc = getattr(delete_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "deleteUser"

    def test_operation_id_with_snake_case_class_name(self):
        """Test operationId generation with snake_case class name."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("user_profiles", __name__)

            @bp.route("/<int:user_profile_id>")
            class UserProfile(MethodView):
                methods = ["GET"]

                def get(self, user_profile_id):
                    return {"profile": {}}

            get_method = getattr(UserProfile, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "getUserProfile"

    def test_manual_operation_id_not_overridden(self):
        """Test that manually set operationId is not overridden."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("users", __name__)

            @bp.route("/<int:user_id>")
            class User(MethodView):
                methods = ["GET"]

                @bp.doc(operationId="customGetUser")
                def get(self, user_id):
                    return {"user": {}}

            get_method = getattr(User, "get")
            apidoc = getattr(get_method, "_apidoc", {})
            # Manual operationId should be preserved
            assert apidoc["manual_doc"]["operationId"] == "customGetUser"

    def test_operation_id_for_function_route(self):
        """Test operationId generation for function-based routes."""
        from flask import Flask

        app = Flask(__name__)

        with app.app_context():
            bp = BlueprintOperationIdMixin("test", __name__)

            @bp.route("/custom")
            def custom_endpoint():
                return {"message": "success"}

            # For function-based routes, use function name
            apidoc = getattr(custom_endpoint, "_apidoc", {})
            assert "manual_doc" in apidoc
            assert "operationId" in apidoc["manual_doc"]
            assert apidoc["manual_doc"]["operationId"] == "customEndpoint"
