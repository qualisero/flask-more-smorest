"""Tests for the health check endpoint."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_more_smorest import __version__, db, init_db
from flask_more_smorest.perms import Api


@pytest.fixture
def api(unit_api: Api) -> Api:
    """Return the API fixture for type compatibility."""
    return unit_api


@pytest.mark.usefixtures("unit_app", "api", "db_session")
class TestHealthEndpointDefault:
    """Tests for default health endpoint configuration."""

    def test_health_endpoint_returns_healthy(self, unit_app: Flask) -> None:
        """Test that health endpoint returns healthy status."""
        with unit_app.test_client() as client:
            response = client.get("/health")

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            assert data["version"] == __version__
            assert "timestamp" in data

    def test_health_endpoint_is_public(self, unit_app: Flask) -> None:
        """Test that health endpoint doesn't require authentication."""
        with unit_app.test_client() as client:
            # No auth headers provided
            response = client.get("/health")

            # Should still work without auth
            assert response.status_code == 200
            assert response.get_json()["status"] == "healthy"


@pytest.mark.usefixtures("app", "db_session")
class TestHealthEndpointCustomPath:
    """Tests for custom health endpoint path configuration."""

    def test_health_endpoint_custom_path(self) -> None:
        """Test that health endpoint path can be customized."""
        from flask import Flask

        from flask_more_smorest.perms import Api

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["JWT_SECRET_KEY"] = "test-secret"
        app.config["API_TITLE"] = "Test API"
        app.config["API_VERSION"] = "v1"
        app.config["OPENAPI_VERSION"] = "3.0.2"
        app.config["HEALTH_ENDPOINT_PATH"] = "/api/health"

        init_db(app)
        Api(app)

        with app.app_context():
            db.create_all()

            with app.test_client() as client:
                # Default path should not exist
                response = client.get("/health")
                assert response.status_code == 404

                # Custom path should work
                response = client.get("/api/health")
                assert response.status_code == 200
                assert response.get_json()["status"] == "healthy"

            db.session.remove()
            db.drop_all()


@pytest.mark.usefixtures("app", "db_session")
class TestHealthEndpointDisabled:
    """Tests for disabling health endpoint."""

    def test_health_endpoint_can_be_disabled(self) -> None:
        """Test that health endpoint can be disabled."""
        from flask import Flask

        from flask_more_smorest.perms import Api

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["JWT_SECRET_KEY"] = "test-secret"
        app.config["API_TITLE"] = "Test API"
        app.config["API_VERSION"] = "v1"
        app.config["OPENAPI_VERSION"] = "3.0.2"
        app.config["HEALTH_ENDPOINT_ENABLED"] = False

        init_db(app)
        Api(app)

        with app.app_context():
            db.create_all()

            with app.test_client() as client:
                response = client.get("/health")
                # Should return 404 since endpoint is disabled
                assert response.status_code == 404

            db.session.remove()
            db.drop_all()
