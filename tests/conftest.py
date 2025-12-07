"""Test configuration and fixtures for flask-more-smorest tests."""

from typing import TYPE_CHECKING
import pytest
from flask import Flask
from flask_smorest import Api
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import Schema

from flask_more_smorest.sqla import db, BaseModel

if TYPE_CHECKING:
    from flask.testing import FlaskClient


@pytest.fixture(scope="function")
def app() -> Flask:
    """Create and configure a test Flask application.

    Returns:
        Configured Flask application instance for testing
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key"

    # Initialize database
    db.init_app(app)

    return app


@pytest.fixture
def api(app: Flask) -> Api:
    """Create a test API instance.

    Args:
        app: Flask application fixture

    Returns:
        Api instance for testing
    """
    return Api(app)


@pytest.fixture
def simple_user_model() -> type[BaseModel]:
    """Create a simple test user model.

    Returns:
        SimpleUser model class for testing
    """

    class SimpleUser(BaseModel):
        """Test user model."""

        __tablename__ = "simple_users"

        username = db.Column(db.String(80), unique=True, nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        is_active = db.Column(db.Boolean, default=True)
        age = db.Column(db.Integer, nullable=True)

        def __repr__(self) -> str:
            return f"<SimpleUser {self.username}>"

    return SimpleUser


@pytest.fixture
def user_schema(simple_user_model: type[BaseModel]) -> type[SQLAlchemyAutoSchema]:
    """Create a test User schema.

    Args:
        simple_user_model: SimpleUser model fixture

    Returns:
        UserSchema class for testing
    """

    class UserSchema(SQLAlchemyAutoSchema):
        """Test user schema."""

        class Meta:
            model = simple_user_model
            load_instance = True
            include_fk = True

    return UserSchema


@pytest.fixture
def sample_users(app: Flask, simple_user_model: type[BaseModel]) -> list[BaseModel]:
    """Create sample user data for testing.

    Args:
        app: Flask application fixture
        simple_user_model: SimpleUser model fixture

    Returns:
        List of created user instances
    """
    with app.app_context():
        db.create_all()

        users = [
            simple_user_model(username="alice", email="alice@example.com", age=25, is_active=True),
            simple_user_model(username="bob", email="bob@example.com", age=30, is_active=False),
            simple_user_model(username="charlie", email="charlie@example.com", age=35, is_active=True),
        ]

        for user in users:
            db.session.add(user)

        db.session.commit()
        return users


@pytest.fixture
def client(app: Flask) -> "FlaskClient":
    """Create a test client.

    Args:
        app: Flask application fixture

    Returns:
        Flask test client
    """
    return app.test_client()


@pytest.fixture
def runner(app: Flask):
    """Create a test CLI runner.

    Args:
        app: Flask application fixture

    Returns:
        Flask CLI test runner
    """
    return app.test_cli_runner()


# Globals that need to be available to modules
globals()["User"] = None
globals()["UserSchema"] = None


def set_test_models(user_model: type[BaseModel], user_schema: type[Schema]) -> None:
    """Set global test models for import by CRUD blueprint.

    Args:
        user_model: User model class to set globally
        user_schema: User schema class to set globally
    """
    globals()["User"] = user_model
    globals()["UserSchema"] = user_schema
