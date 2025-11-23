"""Test configuration and fixtures for flask-smorest-crud tests."""

import pytest
from flask import Flask
from flask_smorest import Api
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import Schema, fields
from datetime import datetime
import uuid

from flask_more_smorest.database import db
from flask_more_smorest import BaseModel


@pytest.fixture(scope="function")
def app():
    """Create and configure a test Flask application."""
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
def api(app):
    """Create a test API instance."""
    return Api(app)


@pytest.fixture
def simple_user_model():
    """Create a simple test user model."""

    from flask_more_smorest.models import BaseModel

    class SimpleUser(BaseModel):
        username = db.Column(db.String(80), unique=True, nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)
        is_active = db.Column(db.Boolean, default=True)
        age = db.Column(db.Integer, nullable=True)

        def __repr__(self):
            return f"<SimpleUser {self.username}>"

    return SimpleUser


@pytest.fixture
def user_schema(simple_user_model):
    """Create a test User schema."""

    class UserSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = simple_user_model
            load_instance = True
            include_fk = True

    return UserSchema


@pytest.fixture
def sample_users(app, simple_user_model):
    """Create sample user data for testing."""
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
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner."""
    return app.test_cli_runner()


# Globals that need to be available to modules
globals()["User"] = None
globals()["UserSchema"] = None


def set_test_models(user_model, user_schema):
    """Set global test models for import by CRUD blueprint."""
    globals()["User"] = user_model
    globals()["UserSchema"] = user_schema
