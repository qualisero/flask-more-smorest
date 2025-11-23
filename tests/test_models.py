"""Tests for BaseModel and related model functionality."""

import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, Mock

from flask_more_smorest.models import BaseModel, BaseSchema, check_create
from flask_more_smorest.database import db
from flask_more_smorest.exceptions import ForbiddenError, NotFoundError


class TestBaseModelClass:
    """Tests for BaseModel class features."""

    def test_basemodel_class_exists(self):
        """Test that BaseModel class exists and has expected attributes."""
        assert BaseModel is not None
        assert hasattr(BaseModel, "__abstract__")

    def test_basemodel_has_required_methods(self):
        """Test that BaseModel has the required permission methods."""
        # These should be defined on the class
        assert hasattr(BaseModel, "can_read")
        assert hasattr(BaseModel, "can_write")
        assert hasattr(BaseModel, "can_create")
        assert hasattr(BaseModel, "_can_read")
        assert hasattr(BaseModel, "_can_write")
        assert hasattr(BaseModel, "_can_create")

    def test_basemodel_has_crud_methods(self):
        """Test that BaseModel has CRUD helper methods."""
        assert hasattr(BaseModel, "get")
        assert hasattr(BaseModel, "get_or_404")
        assert hasattr(BaseModel, "get_by")
        assert hasattr(BaseModel, "get_by_or_404")
        assert hasattr(BaseModel, "save")
        assert hasattr(BaseModel, "update")
        assert hasattr(BaseModel, "delete")


class TestBaseModelConcrete:
    """Tests using a concrete BaseModel implementation."""

    @pytest.fixture(scope="function") 
    def test_model(self, app):
        """Create a concrete test model for testing."""
        import time
        import random
        import threading
        from flask_more_smorest.database import db

        # Use unique class name to avoid SQLAlchemy registry conflicts
        thread_id = threading.get_ident() 
        timestamp = int(time.time() * 1000000)
        random_id = random.randint(1000, 9999)
        class_name = f"TestModel_{thread_id}_{timestamp}_{random_id}"
        table_name = f"test_table_{thread_id}_{timestamp}_{random_id}"

        # Create test model dynamically to avoid registry warnings
        from flask_more_smorest.models import BaseModel
        
        TestModel = type(class_name, (BaseModel,), {
            '__tablename__': table_name,
            '__module__': f"test_models_{thread_id}_{timestamp}",
            'name': db.Column(db.String(80), nullable=False),
            '_can_write': lambda self: True,
            '_can_read': lambda self: True,  
            '_can_create': lambda self: True
        })

        with app.app_context():
            # Create table for this test
            TestModel.__table__.create(db.engine, checkfirst=True)
            
            # Clean up table after test
            def cleanup():
                try:
                    TestModel.__table__.drop(db.engine, checkfirst=True)
                except Exception:
                    pass
            
            # Register cleanup (pytest will handle this)
            import atexit
            atexit.register(cleanup)

        return TestModel

    def test_concrete_model_creation(self, app, test_model):
        """Test creating an instance of a concrete BaseModel."""
        with app.app_context():
            with test_model.bypass_perms():
                instance = test_model(name="test")
                instance.save()

                assert instance.id is not None
                assert instance.name == "test"
                assert instance.created_at is not None
                assert instance.updated_at is not None

    def test_concrete_model_schema(self, app, test_model):
        """Test schema generation for concrete model."""
        with app.app_context():
            schema = test_model.Schema()
            assert schema is not None
            assert "is_writable" in schema.fields


class TestBaseSchema:
    """Tests for BaseSchema functionality."""

    def test_baseschema_class_exists(self):
        """Test that BaseSchema class exists."""
        assert BaseSchema is not None

    def test_baseschema_has_writable_field(self):
        """Test that BaseSchema includes is_writable field definition."""
        # Check the field is defined in the class fields
        schema = BaseSchema()
        assert "is_writable" in schema.fields


class TestCheckCreate:
    """Tests for check_create utility function."""

    def test_check_create_with_non_models(self):
        """Test check_create with non-BaseModel objects."""
        # Should not raise exception for non-models
        check_create(["string", 123, {"dict": "value"}])

    def test_check_create_with_empty_list(self):
        """Test check_create with empty list."""
        check_create([])

    def test_check_create_with_none(self):
        """Test check_create with None values."""
        check_create([None])


class TestBaseModelPermissions:
    """Test BaseModel permission system."""

    def test_permission_bypass_context_manager(self):
        """Test that bypass_perms is available as class method."""
        assert hasattr(BaseModel, "bypass_perms")

        # Test the context manager exists (can't test functionality without concrete model)
        try:
            with BaseModel.bypass_perms():
                pass
        except Exception:
            # This is expected since BaseModel is abstract
            pass
