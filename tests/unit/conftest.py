"""Shared fixtures for unit tests."""

from collections.abc import Generator

import pytest
from flask import Flask

from flask_more_smorest import Api, db, init_db, init_jwt
from flask_more_smorest.error.error_handlers import RequestHandlers
from flask_more_smorest.perms import init_fms
from flask_more_smorest.perms.models import defaults as defaults_module


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Base Flask app fixture for unit tests."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key"

    from flask_more_smorest.perms import clear_registration

    clear_registration()
    init_fms(
        user=defaults_module.DefaultUser,
        role=defaults_module.DefaultUserRole,
        token=defaults_module.DefaultToken,
        domain=defaults_module.DefaultDomain,
        setting=defaults_module.DefaultUserSetting,
    )
    init_db(app)
    init_jwt(app)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def unit_app() -> Generator[Flask, None, None]:
    """Flask app with extended config for API testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key"

    from flask_more_smorest.perms import clear_registration

    clear_registration()
    init_fms(
        user=defaults_module.DefaultUser,
        role=defaults_module.DefaultUserRole,
        token=defaults_module.DefaultToken,
        domain=defaults_module.DefaultDomain,
        setting=defaults_module.DefaultUserSetting,
    )
    init_db(app)
    init_jwt(app)
    RequestHandlers(app)  # Register error handlers

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def unit_api(unit_app: Flask) -> Api:
    """Flask-Smorest API instance for unit tests."""
    return Api(unit_app)


@pytest.fixture
def db_session(app: Flask) -> Generator[None, None, None]:
    """Database session fixture that creates and drops tables.

    Note: This fixture yields None. Use db.session for database operations.
    """
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def reset_user_context() -> None:
    """Fixture that clears user context registration before each test.

    Tests that need to clear registration mid-test should call clear_registration() manually.
    """
    from flask_more_smorest.perms import clear_registration

    clear_registration()
    return
