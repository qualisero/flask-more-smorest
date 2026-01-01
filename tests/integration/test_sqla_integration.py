"""Integration tests for SQLAlchemy integration.

This module tests the BaseModel, database initialization, and migration utilities.
"""

import uuid
from datetime import datetime

import pytest
from flask import Flask

from flask_more_smorest import BaseModel, db, init_db


@pytest.fixture(scope="function")
def app() -> Flask:
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize database
    init_db(app)

    return app


class Product(BaseModel):
    """A simple product model for testing."""

    __tablename__ = "products"

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    count = db.Column(db.Integer, default=0)


@pytest.fixture(scope="function")
def test_model(app: Flask) -> type[Product]:
    """Create a test model class."""

    rand_str = uuid.uuid4().hex
    class_name = f"Product_{rand_str}"
    table_name = f"products_{rand_str}"

    TestItem = type(
        class_name,
        (Product,),
        {
            "__tablename__": table_name,
            "__module__": __name__,
        },
    )

    with app.app_context():
        db.create_all()

    return TestItem


class TestBaseModelIntegration:
    """Integration tests for BaseModel."""

    def test_base_model_has_id(self, app: Flask, test_model: type[BaseModel]) -> None:
        """Test that BaseModel instances have UUIDs."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            db.session.add(item)
            db.session.commit()

            assert item.id is not None
            assert isinstance(item.id, uuid.UUID)

    def test_base_model_has_timestamps(self, app: Flask, test_model: type[BaseModel]) -> None:
        """Test that BaseModel instances have created_at and updated_at timestamps."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            db.session.add(item)
            db.session.commit()

            assert item.created_at is not None
            assert isinstance(item.created_at, datetime)
            assert item.updated_at is not None
            assert isinstance(item.updated_at, datetime)

    def test_base_model_save_method(self, app: Flask, test_model: type[Product]) -> None:
        """Test the save convenience method."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            item.save()

            # Item should be persisted
            assert item.id is not None
            retrieved = db.session.get(test_model, item.id)
            assert retrieved is not None
            assert retrieved.name == "Test Item"

    def test_base_model_update_method(self, app: Flask, test_model: type[Product]) -> None:
        """Test the update convenience method."""
        with app.app_context():
            item = test_model(name="Original Name", count=5)
            item.save()
            original_updated_at = item.updated_at

            # Update the item
            item.update(name="Updated Name", count=10)

            assert item.name == "Updated Name"
            assert item.count == 10
            # updated_at should be newer
            assert item.updated_at >= original_updated_at

    def test_base_model_delete_method(self, app: Flask, test_model: type[Product]) -> None:
        """Test the delete method."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            item.save()
            item_id = item.id

            # Delete the item
            item.delete()

            # Item should be gone
            retrieved = db.session.get(test_model, item_id)
            assert retrieved is None

    def test_base_model_get_method(self, app: Flask, test_model: type[Product]) -> None:
        """Test the get class method."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            item.save()
            item_id = item.id

            # Retrieve using get method
            retrieved = test_model.get(item_id)
            assert retrieved is not None
            assert retrieved.id == item_id
            assert retrieved.name == "Test Item"

    def test_base_model_get_or_404_success(self, app: Flask, test_model: type[Product]) -> None:
        """Test get_or_404 with existing item."""
        with app.app_context():
            item = test_model(name="Test Item", count=5)
            item.save()
            item_id = item.id

            # Should retrieve successfully
            retrieved = test_model.get_or_404(item_id)
            assert retrieved.id == item_id

    def test_base_model_get_or_404_not_found(self, app: Flask, test_model: type[Product]) -> None:
        """Test get_or_404 with non-existent item."""
        from flask_more_smorest.error.exceptions import NotFoundError

        with app.app_context():
            non_existent_id = uuid.uuid4()

            # Should raise NotFoundError
            with pytest.raises(NotFoundError):
                test_model.get_or_404(non_existent_id)

    def test_base_model_get_by_method(self, app: Flask, test_model: type[Product]) -> None:
        """Test the get_by method for filtering."""
        with app.app_context():
            item1 = test_model(name="Item One", count=1)
            item2 = test_model(name="Item Two", count=2)
            item1.save()
            item2.save()

            # Find by name
            result = test_model.get_by(name="Item One")
            assert result is not None
            assert result.name == "Item One"

            # Find by count
            result = test_model.get_by(count=2)
            assert result is not None
            assert result.name == "Item Two"

    def test_base_model_get_by_or_404(self, app: Flask, test_model: type[Product]) -> None:
        """Test get_by_or_404 method."""
        from flask_more_smorest.error.exceptions import NotFoundError

        with app.app_context():
            item = test_model(name="Test Item", count=5)
            item.save()

            # Should retrieve successfully
            retrieved = test_model.get_by_or_404(name="Test Item")
            assert retrieved.name == "Test Item"

            # Should raise NotFoundError
            with pytest.raises(NotFoundError):
                test_model.get_by_or_404(name="Non-existent")

    def test_base_model_schema_generation(self, app: Flask, test_model: type[Product]) -> None:
        """Test that BaseModel generates a Schema class."""
        with app.app_context():
            schema_class = test_model.Schema
            assert schema_class is not None

            schema = schema_class()
            assert "id" in schema.fields
            assert "created_at" in schema.fields
            assert "updated_at" in schema.fields
            assert "name" in schema.fields
            assert "is_writable" in schema.fields


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_init_db_creates_tables(self) -> None:
        """Test that init_db creates database tables."""
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

        init_db(app)

        # Database should be initialized - check that we can create tables
        with app.app_context():
            # Should be able to create tables without error
            db.create_all()
            # No exception means success
            assert True

    def test_db_is_flask_sqlalchemy_instance(self, app: Flask) -> None:
        """Test that db is a Flask-SQLAlchemy instance."""
        from flask_sqlalchemy import SQLAlchemy

        assert isinstance(db, SQLAlchemy)

    def test_multiple_models_can_be_created(self, app: Flask) -> None:
        """Test creating multiple model classes."""

        class Model1(BaseModel):
            __tablename__ = "model1"
            field1 = db.Column(db.String(50))

            def _can_read(self) -> bool:
                return True

            def _can_write(self) -> bool:
                return True

            def _can_create(self) -> bool:
                return True

        class Model2(BaseModel):
            __tablename__ = "model2"
            field2 = db.Column(db.Integer)

            def _can_read(self) -> bool:
                return True

            def _can_write(self) -> bool:
                return True

            def _can_create(self) -> bool:
                return True

        with app.app_context():
            db.create_all()

            with Model1.bypass_perms(), Model2.bypass_perms():
                # Both models should work
                item1 = Model1(field1="test")
                item1.save()

                item2 = Model2(field2=42)
                item2.save()

                assert item1.id is not None
                assert item2.id is not None
