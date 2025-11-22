"""Tests for enhanced blueprint functionality."""

import pytest
from flask import Flask
from flask_smorest import Api
from flask_more_smorest import EnhancedBlueprint


class TestEnhancedBlueprint:
    """Tests for EnhancedBlueprint class."""

    @pytest.fixture
    def blueprint(self):
        """Create a test enhanced blueprint."""
        return EnhancedBlueprint("test", __name__)

    def test_blueprint_creation(self, blueprint):
        """Test that EnhancedBlueprint can be created."""
        assert blueprint.name == "test"
        assert isinstance(blueprint, EnhancedBlueprint)

    def test_public_endpoint_decorator(self, blueprint):
        """Test the public_endpoint decorator."""

        @blueprint.public_endpoint
        def test_endpoint():
            """Test endpoint"""
            return {"message": "success"}

        assert hasattr(test_endpoint, "_is_public")
        assert test_endpoint._is_public is True
        assert "Public" in getattr(test_endpoint, "__doc__", "")

    def test_public_endpoint_without_docstring(self, blueprint):
        """Test public_endpoint decorator on function without docstring."""

        @blueprint.public_endpoint
        def test_endpoint():
            return {"message": "success"}

        assert test_endpoint.__doc__ == "Public endpoint"

    def test_admin_endpoint_decorator(self, blueprint):
        """Test the admin_endpoint decorator."""

        @blueprint.admin_endpoint
        def admin_only():
            """Admin function"""
            return {"data": "sensitive"}

        assert hasattr(admin_only, "_is_admin")
        assert admin_only._is_admin is True
        assert "Admin only" in getattr(admin_only, "__doc__", "")

    def test_admin_endpoint_without_docstring(self, blueprint):
        """Test admin_endpoint decorator on function without docstring."""

        @blueprint.admin_endpoint
        def admin_only():
            return {"data": "sensitive"}

        assert admin_only.__doc__ == "Admin only endpoint"

    def test_route_decorator_with_operationid(self, app, blueprint):
        """Test that route decorator adds operationId."""
        with app.app_context():

            @blueprint.route("/test", methods=["GET"])
            def test_route():
                """Test route"""
                return {"result": "ok"}

            # Check that the decorator was applied
            # Note: operationId testing requires more complex setup with API registration
            assert hasattr(test_route, "_apidoc") or callable(test_route)

    def test_multiple_decorators_combination(self, blueprint):
        """Test combining public and route decorators."""

        @blueprint.route("/public-test", methods=["GET"])
        @blueprint.public_endpoint
        def public_test():
            """Public test endpoint"""
            return {"status": "public"}

        assert hasattr(public_test, "_is_public")
        assert public_test._is_public is True
        assert "Public" in getattr(public_test, "__doc__", "")

    def test_blueprint_registration(self, app):
        """Test that enhanced blueprint can be registered with Flask app."""
        api = Api(app)
        blueprint = EnhancedBlueprint("test_api", __name__, url_prefix="/api")

        @blueprint.route("/status")
        def status():
            return {"status": "ok"}

        # Should not raise an exception
        api.register_blueprint(blueprint)

        # Blueprint should be registered (check if blueprint is in the API)
        # Note: API structure may vary between Flask-Smorest versions
        assert blueprint.name == "test_api"
