"""Tests for the unified schema resolver function."""

from __future__ import annotations

import pytest
from marshmallow import Schema, fields

from flask_more_smorest.crud.crud_blueprint import resolve_schema


class SampleSchema(Schema):
    """Sample schema for resolver tests."""

    name = fields.String()
    value = fields.Integer()


class AnotherSampleSchema(Schema):
    """Another sample schema."""

    id = fields.Integer()


class TestResolveSchema:
    """Tests for resolve_schema function."""

    def test_resolve_schema_class(self) -> None:
        """Test resolving a Schema class directly."""
        result = resolve_schema(SampleSchema, "")
        assert result is SampleSchema

    def test_resolve_schema_instance(self) -> None:
        """Test resolving a Schema instance returns its class."""
        instance = SampleSchema()
        result = resolve_schema(instance, "")
        assert result is SampleSchema

    def test_resolve_none_with_default(self) -> None:
        """Test resolving None returns the default schema."""
        result = resolve_schema(None, "", default_schema=SampleSchema)
        assert result is SampleSchema

    def test_resolve_none_without_default_raises(self) -> None:
        """Test resolving None without default raises ValueError."""
        with pytest.raises(ValueError, match="No schema provided"):
            resolve_schema(None, "")

    def test_resolve_none_with_context_in_error(self) -> None:
        """Test that context is included in error message."""
        with pytest.raises(ValueError, match="for PATCH method"):
            resolve_schema(None, "", context="PATCH method")

    def test_resolve_string_from_module(self) -> None:
        """Test resolving a string schema name from a module."""
        # Use the test module itself as the import path
        result = resolve_schema(
            "SampleSchema",
            "tests.unit.test_schema_resolver",
        )
        # The resolved class should have the same name
        assert result.__name__ == "SampleSchema"
        assert issubclass(result, Schema)

    def test_resolve_string_module_not_found(self) -> None:
        """Test that invalid module path raises ValueError."""
        with pytest.raises(ValueError, match="Could not import module"):
            resolve_schema("SomeSchema", "nonexistent.module.path")

    def test_resolve_string_attribute_not_found(self) -> None:
        """Test that missing schema in module raises ValueError."""
        with pytest.raises(ValueError, match="Could not find schema"):
            resolve_schema("NonExistentSchema", "tests.unit.test_schema_resolver")

    def test_resolve_string_not_schema_subclass(self) -> None:
        """Test that importing non-Schema raises TypeError."""
        # 'pytest' is in the module but not a Schema subclass
        with pytest.raises(TypeError) as exc_info:
            resolve_schema("pytest", "tests.unit.test_schema_resolver")

        assert "must be a Schema subclass" in str(exc_info.value)

    def test_resolve_invalid_type_raises(self) -> None:
        """Test that invalid types raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            resolve_schema(123, "")  # pyright: ignore[reportArgumentType]

        assert "must be a string, Schema subclass, or Schema instance" in str(exc_info.value)

    def test_resolve_with_context_in_type_error(self) -> None:
        """Test that context is included in TypeError message."""
        with pytest.raises(TypeError) as exc_info:
            resolve_schema(123, "", context="POST method")  # pyright: ignore[reportArgumentType]

        assert "for POST method" in str(exc_info.value)

    def test_resolve_non_schema_class_raises(self) -> None:
        """Test that non-Schema classes raise TypeError."""

        class NotASchema:
            pass

        with pytest.raises(TypeError) as exc_info:
            resolve_schema(NotASchema, "")  # pyright: ignore[reportArgumentType]

        assert "must be a string, Schema subclass, or Schema instance" in str(exc_info.value)

    def test_resolve_prefers_candidate_over_default(self) -> None:
        """Test that explicit candidate takes precedence over default."""
        result = resolve_schema(AnotherSampleSchema, "", default_schema=SampleSchema)
        assert result is AnotherSampleSchema
