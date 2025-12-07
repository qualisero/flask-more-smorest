"""Integration tests for CRUD functionality.

This module tests the complete CRUD blueprint functionality with a real Flask app,
using up-to-date features from flask-smorest, SQLAlchemy, and marshmallow_sqlalchemy.
"""

from typing import TYPE_CHECKING, Iterator

import pytest
import uuid
from flask import Flask
from apispec.ext.marshmallow import MarshmallowPlugin, resolver as default_resolver
from flask_smorest import Api

from flask_more_smorest import CRUDBlueprint, BaseModel, db, init_db

if TYPE_CHECKING:
    from flask.testing import FlaskClient


@pytest.fixture(scope="function")
def app() -> Flask:
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "CRUD Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key-crud"

    # Initialize database
    init_db(app)

    return app


def custom_schema_name_resolver(schema, **kwargs: str | bool) -> str:
    """Custom schema name resolver that appends 'Partial' for partial schemas."""
    if getattr(schema, "partial", False):
        return default_resolver(schema) + "Partial"
    return default_resolver(schema)


@pytest.fixture(scope="function")
def api(app: Flask) -> Api:
    """Create API instance."""
    # NOTE: this is automatically added when using flask_more_smorest.Api instead of flask_smorest.Api
    ma_plugin = MarshmallowPlugin(schema_name_resolver=custom_schema_name_resolver)
    spec_kwargs = {"marshmallow_plugin": ma_plugin}

    return Api(app, spec_kwargs=spec_kwargs)


@pytest.fixture(scope="function")
def product_model(app: Flask) -> type[BaseModel]:
    """Create a Product model for testing."""

    rand_str = uuid.uuid4().hex
    class_name = f"Product_{rand_str}"
    table_name = f"products_{rand_str}"

    ProductModel = type(
        class_name,
        (BaseModel,),
        {
            "__tablename__": table_name,
            "__module__": __name__,
            "name": db.Column(db.String(100), nullable=False),
            "description": db.Column(db.String(500)),
            "price": db.Column(db.Float, nullable=False),
            "in_stock": db.Column(db.Boolean, default=True),
            "_can_read": lambda self: True,
            "_can_write": lambda self: True,
            "_can_create": classmethod(lambda cls: True),
        },
    )

    with app.app_context():
        db.create_all()

    return ProductModel


@pytest.fixture(scope="function")
def product_blueprint(product_model: type[BaseModel]) -> Iterator[CRUDBlueprint]:
    """Create a CRUD blueprint for Product."""
    # We need to set up a mock module for the blueprint to import from
    import sys
    import types

    # Create a mock module
    mock_module = types.ModuleType("mock_module")
    # randstr = uuid.uuid4().hex
    setattr(mock_module, product_model.__name__, product_model)
    sys.modules["mock_module"] = mock_module

    try:
        blueprint = CRUDBlueprint(
            "products",
            __name__,
            model=product_model.__name__,
            model_import_name="mock_module",
            schema_import_name="mock_module",
            url_prefix="/api/products/",
        )
        yield blueprint
    finally:
        # Cleanup
        if "mock_module" in sys.modules:
            del sys.modules["mock_module"]


@pytest.fixture
def client(app: Flask, api: Api, product_blueprint: CRUDBlueprint) -> "FlaskClient":
    """Create test client with registered blueprint."""
    api.register_blueprint(product_blueprint)
    return app.test_client()


class TestCRUDIntegration:
    """Integration tests for CRUD operations."""

    def test_list_products_empty(self, client: "FlaskClient", app: Flask) -> None:
        """Test listing products when database is empty."""
        with app.app_context():
            response = client.get("/api/products/")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) == 0

    def test_create_product(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test creating a new product."""
        with app.app_context():
            with product_model.bypass_perms():
                product_data = {
                    "name": "Test Product",
                    "description": "A test product",
                    "price": 29.99,
                    "in_stock": True,
                }
                response = client.post("/api/products/", json=product_data)
                # CRUD blueprint returns 200 for POST
                assert response.status_code == 200

                data = response.get_json()
                assert data["name"] == "Test Product"
                assert data["description"] == "A test product"
                assert data["price"] == 29.99
                assert data["in_stock"] is True
                assert "id" in data
                # ID is returned as string
                assert isinstance(data["id"], str)

    def test_get_product(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test retrieving a specific product."""
        with app.app_context():
            with product_model.bypass_perms():
                # Create a product first
                product = product_model(
                    name="Test Product",
                    description="A test product",
                    price=29.99,
                    in_stock=True,
                )
                db.session.add(product)
                db.session.commit()
                product_id = str(product.id)  # Convert to string for comparison

                # Retrieve it
                response = client.get(f"/api/products/{product_id}")
                assert response.status_code == 200

                data = response.get_json()
                # ID is returned as string in JSON
                assert data["id"] == product_id
                assert data["name"] == "Test Product"
                assert data["price"] == 29.99

    def test_update_product(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test updating a product."""
        with app.app_context():
            with product_model.bypass_perms():
                # Create a product first
                product = product_model(
                    name="Test Product",
                    description="A test product",
                    price=29.99,
                    in_stock=True,
                )
                db.session.add(product)
                db.session.commit()
                product_id = str(product.id)

                # Update it
                update_data = {"price": 39.99, "in_stock": False}
                response = client.patch(f"/api/products/{product_id}", json=update_data)
                assert response.status_code == 200

                data = response.get_json()
                assert data["id"] == product_id
                assert data["price"] == 39.99
                assert data["in_stock"] is False
                # Name should remain unchanged
                assert data["name"] == "Test Product"

    def test_delete_product(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test deleting a product."""
        with app.app_context():
            with product_model.bypass_perms():
                # Create a product first
                product = product_model(
                    name="Test Product",
                    description="A test product",
                    price=29.99,
                    in_stock=True,
                )
                db.session.add(product)
                db.session.commit()
                product_id = str(product.id)

                # Delete it
                response = client.delete(f"/api/products/{product_id}")
                assert response.status_code in [200, 204]  # Accept both

                # Verify it's gone - check in database
                deleted_product = db.session.get(product_model, uuid.UUID(product_id))
                assert deleted_product is None

    def test_list_multiple_products(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test listing multiple products."""
        with app.app_context():
            with product_model.bypass_perms():
                # Create multiple products
                products_data = [
                    {"name": "Product 1", "description": "First", "price": 10.00, "in_stock": True},
                    {"name": "Product 2", "description": "Second", "price": 20.00, "in_stock": True},
                    {"name": "Product 3", "description": "Third", "price": 30.00, "in_stock": False},
                ]

                for data in products_data:
                    product = product_model(**data)
                    db.session.add(product)
                db.session.commit()

                # List all products
                response = client.get("/api/products/")
                assert response.status_code == 200

                data = response.get_json()
                assert isinstance(data, list)
                assert len(data) == 3

    def test_filter_products(self, client: "FlaskClient", app: Flask, product_model: type[BaseModel]) -> None:
        """Test filtering products."""
        with app.app_context():
            with product_model.bypass_perms():
                # Create products with different attributes
                products_data = [
                    {"name": "Product 1", "description": "In stock", "price": 10.00, "in_stock": True},
                    {"name": "Product 2", "description": "In stock", "price": 20.00, "in_stock": True},
                    {"name": "Product 3", "description": "Out of stock", "price": 30.00, "in_stock": False},
                ]

                for data in products_data:
                    product = product_model(**data)
                    db.session.add(product)
                db.session.commit()

                # Filter for in-stock products
                response = client.get("/api/products/?in_stock=true")
                assert response.status_code == 200

                data = response.get_json()
                assert len(data) == 2
                assert all(p["in_stock"] is True for p in data)

    def test_create_product_validation_error(self, client: "FlaskClient", app: Flask) -> None:
        """Test creating a product with validation errors."""
        with app.app_context():
            # Missing required fields
            product_data = {
                "description": "Missing name and price",
            }
            response = client.post("/api/products/", json=product_data)
            # Should return 422 for validation errors
            assert response.status_code == 422
