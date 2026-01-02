"""Unit tests for query filtering functionality."""

import enum
from datetime import date, datetime

import pytest
from marshmallow import Schema, fields
from sqlalchemy import Boolean, Column, Date, Integer, String

from flask_more_smorest.crud.query_filtering import generate_filter_schema, get_statements_from_filters
from flask_more_smorest.sqla.base_model import BaseModel


class QueryTestModel(BaseModel):
    """Test model for filtering tests."""

    name = Column(String(50))
    birth_date = Column(Date)
    is_active = Column(Boolean)
    age = Column(Integer)


class QueryTestSchema(Schema):
    """Test schema for filter generation."""

    id = fields.Integer()
    name = fields.String()
    created_at = fields.DateTime()
    birth_date = fields.Date()
    is_active = fields.Boolean()
    age = fields.Integer()
    price = fields.Float()


class FloatOnlySchema(Schema):
    price = fields.Float()


class EnumSchema(Schema):
    class Status(enum.Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"

    status = fields.Enum(Status)


class TestGenerateFilterSchema:
    """Tests for generate_filter_schema function."""

    def test_basic_filter_schema_generation(self) -> None:
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

        # DateTime and float fields should be removed
        assert "created_at" not in filter_schema.fields
        assert "price" not in filter_schema.fields

    def test_filter_schema_field_types(self) -> None:
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
        assert isinstance(filter_schema.fields["price__min"], fields.Float)
        assert isinstance(filter_schema.fields["price__max"], fields.Float)

    def test_filter_schema_field_properties(self) -> None:
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

        price_min = filter_schema.fields["price__min"]
        price_max = filter_schema.fields["price__max"]
        assert price_min.required is False
        assert price_max.required is False

    def test_filter_schema_with_date_field(self) -> None:
        """Test filter schema generation with Date fields."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        # Should have range fields for Date
        assert "birth_date__from" in filter_schema.fields
        assert "birth_date__to" in filter_schema.fields
        assert "birth_date" not in filter_schema.fields

        # Range fields should be Date type
        assert isinstance(filter_schema.fields["birth_date__from"], fields.Date)
        assert isinstance(filter_schema.fields["birth_date__to"], fields.Date)

    def test_filter_schema_preserves_non_temporal_fields(self) -> None:
        """Test that non-temporal fields are preserved as-is."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        # String, Integer, Boolean fields should remain unchanged
        assert "name" in filter_schema.fields
        assert isinstance(filter_schema.fields["name"], fields.String)
        assert "age" in filter_schema.fields
        assert isinstance(filter_schema.fields["age"], fields.Integer)
        assert "is_active" in filter_schema.fields
        assert isinstance(filter_schema.fields["is_active"], fields.Boolean)
        assert "price__min" in filter_schema.fields
        assert "price__max" in filter_schema.fields
        assert "price" not in filter_schema.fields

    def test_generate_filter_schema_does_not_mutate_base_schema(self) -> None:
        """Calling helper should not alter the base schema class or instance."""
        base_schema = QueryTestSchema()
        original_fields = set(base_schema.fields.keys())

        generate_filter_schema(QueryTestSchema)

        assert set(base_schema.fields.keys()) == original_fields
        assert "created_at" in base_schema.fields
        assert "price" in base_schema.fields

    def test_generate_filter_schema_accepts_schema_instance(self) -> None:
        """Passing a schema instance should behave equivalent to passing class."""
        filter_cls_from_instance = generate_filter_schema(QueryTestSchema())
        filter_cls_from_class = generate_filter_schema(QueryTestSchema)

        assert set(filter_cls_from_instance().fields.keys()) == set(filter_cls_from_class().fields.keys())

    def test_generate_filter_schema_float_field_only(self) -> None:
        """Float fields should be replaced with min/max filters only."""
        filter_schema_class = generate_filter_schema(FloatOnlySchema)
        filter_schema = filter_schema_class()

        assert "price__min" in filter_schema.fields
        assert "price__max" in filter_schema.fields
        assert "price" not in filter_schema.fields

    def test_generate_filter_schema_enum_support(self) -> None:
        """Enum fields should expose __in list filters."""
        filter_schema_class = generate_filter_schema(EnumSchema)
        filter_schema = filter_schema_class()

        assert "status__in" in filter_schema.fields
        assert isinstance(filter_schema.fields["status__in"], fields.List)

    def test_filter_schema_includes_pagination_fields(self) -> None:
        """Pagination parameters should always be available and optional."""
        filter_schema_class = generate_filter_schema(QueryTestSchema)
        filter_schema = filter_schema_class()

        assert "page" in filter_schema.fields
        assert "page_size" in filter_schema.fields
        assert filter_schema.fields["page"].required is False
        assert filter_schema.fields["page_size"].required is False


class TestGetStatementsFromFilters:
    """Tests for get_statements_from_filters function."""

    def test_basic_equality_filter(self) -> None:
        """Test basic equality filtering."""
        filters_dict = {"name": "John", "is_active": True}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2
        # Statements should be SQLAlchemy expressions

    def test_range_filtering_datetime(self) -> None:
        """Test range filtering with __from and __to suffixes for DateTime."""
        filters_dict = {
            "created_at__from": datetime(2024, 1, 1),
            "created_at__to": datetime(2024, 12, 31),
        }
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2

    def test_range_filtering_date(self) -> None:
        """Test range filtering with __from and __to suffixes for Date."""
        filters_dict = {
            "birth_date__from": date(2000, 1, 1),
            "birth_date__to": date(2005, 12, 31),
        }
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2

    def test_min_max_filtering(self) -> None:
        """Test min/max filtering with __min and __max suffixes."""
        filters_dict = {"age__min": 18, "age__max": 65}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 2

    def test_none_values_ignored(self) -> None:
        """Test that None values are ignored in filtering."""
        filters_dict = {"name": None, "age": 25, "is_active": None}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        # Only age filter should be included
        assert len(statements) == 1

    def test_mixed_filter_types(self) -> None:
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

    def test_empty_filters(self) -> None:
        """Test with empty filters dictionary."""
        statements = get_statements_from_filters({}, QueryTestModel)
        assert len(statements) == 0

    def test_invalid_field_names(self) -> None:
        """Test handling of invalid field names."""
        filters_dict = {"nonexistent_field": "value"}

        # Should raise AttributeError for nonexistent fields
        with pytest.raises(AttributeError):
            get_statements_from_filters(filters_dict, QueryTestModel)

    def test_from_only_filter(self) -> None:
        """Test range filter with only __from suffix."""
        filters_dict = {"created_at__from": datetime(2024, 1, 1)}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 1

    def test_to_only_filter(self) -> None:
        """Test range filter with only __to suffix."""
        filters_dict = {"created_at__to": datetime(2024, 12, 31)}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 1

    def test_min_only_filter(self) -> None:
        """Test min filter without max."""
        filters_dict = {"age__min": 18}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 1

    def test_max_only_filter(self) -> None:
        """Test max filter without min."""
        filters_dict = {"age__max": 65}
        statements = get_statements_from_filters(filters_dict, QueryTestModel)

        assert len(statements) == 1
