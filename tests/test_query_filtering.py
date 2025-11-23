"""Tests for query filtering functionality."""

import pytest
from datetime import datetime, date
from marshmallow import fields, Schema
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase
from flask_more_smorest.query_filtering import generate_filter_schema, get_statements_from_filters


class Base(DeclarativeBase):
    """Test SQLAlchemy base class."""

    pass


class QueryTestModel(Base):
    """Test model for filtering tests."""

    __tablename__ = "query_test_model"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    created_at = Column(DateTime)
    is_active = Column(Boolean)
    age = Column(Integer)


class QueryTestSchema(Schema):
    """Test schema for filter generation."""

    id = fields.Integer()
    name = fields.String()
    created_at = fields.DateTime()
    is_active = fields.Boolean()
    age = fields.Integer()


class TestGenerateFilterSchema:
    """Tests for generate_filter_schema function."""

    def test_basic_filter_schema_generation(self):
        """Test generating a filter schema from base schema."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        # Should have original fields
        assert "name" in filter_schema.fields
        assert "is_active" in filter_schema.fields
        assert "age" in filter_schema.fields

        # Should have range fields for DateTime
        assert "created_at__from" in filter_schema.fields
        assert "created_at__to" in filter_schema.fields

        # DateTime field should be removed
        assert "created_at" not in filter_schema.fields

    def test_filter_schema_field_types(self):
        """Test that filter schema maintains correct field types."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        # Range fields should maintain original field type
        assert isinstance(filter_schema.fields["created_at__from"], fields.DateTime)
        assert isinstance(filter_schema.fields["created_at__to"], fields.DateTime)

        # Other fields should maintain their types
        assert isinstance(filter_schema.fields["name"], fields.String)
        assert isinstance(filter_schema.fields["age"], fields.Integer)
        assert isinstance(filter_schema.fields["is_active"], fields.Boolean)

    def test_filter_schema_field_properties(self):
        """Test that filter schema fields have correct properties."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        # Range fields should be optional
        created_from = filter_schema.fields["created_at__from"]
        created_to = filter_schema.fields["created_at__to"]

        assert created_from.load_default is None
        assert created_to.load_default is None
        assert created_from.required is False
        assert created_to.required is False

    def test_filter_schema_with_date_field(self):
        """Test filter schema generation with Date fields."""

        class DateSchema(Schema):
            birth_date = fields.Date()
            name = fields.String()

        filter_schema_class = generate_filter_schema(DateSchema)
        filter_schema = filter_schema_class()

        # Should have range fields for Date
        assert "birth_date__from" in filter_schema.fields
        assert "birth_date__to" in filter_schema.fields
        assert "birth_date" not in filter_schema.fields

        # Range fields should be Date type
        assert isinstance(filter_schema.fields["birth_date__from"], fields.Date)
        assert isinstance(filter_schema.fields["birth_date__to"], fields.Date)


class TestGetStatementsFromFilters:
    """Tests for get_statements_from_filters function."""

    def test_basic_equality_filter(self):
        """Test basic equality filtering."""
        filters_dict = {"name": "John", "is_active": True}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2
        # Note: Actual SQLAlchemy statement testing would require more setup

    def test_range_filtering(self):
        """Test range filtering with __from and __to suffixes."""
        filters_dict = {"created_at__from": datetime(2024, 1, 1), "created_at__to": datetime(2024, 12, 31)}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2

    def test_min_max_filtering(self):
        """Test min/max filtering with __min and __max suffixes."""
        filters_dict = {"age__min": 18, "age__max": 65}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2

    def test_none_values_ignored(self):
        """Test that None values are ignored in filtering."""
        filters_dict = {"name": None, "age": 25, "is_active": None}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        # Only age filter should be included
        assert len(statements) == 1

    def test_mixed_filter_types(self):
        """Test combining different filter types."""
        filters_dict = {
            "name": "John",
            "age__min": 18,
            "age__max": 65,
            "created_at__from": datetime(2024, 1, 1),
            "is_active": True,
        }
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 5

    def test_empty_filters(self):
        """Test with empty filters dictionary."""
        statements = get_statements_from_filters({}, QueryTestModel)
        assert len(statements) == 0

    def test_invalid_field_names(self):
        """Test handling of invalid field names."""
        filters_dict = {"nonexistent_field": "value"}

        # Should raise AttributeError for nonexistent fields
        with pytest.raises(AttributeError):
            get_statements_from_filters(filters_dict, QueryTestModel)
