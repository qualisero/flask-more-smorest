"""Unit tests for utility functions."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from flask import Flask
from marshmallow import ValidationError, fields
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import BaseModel, BaseSchema, db
from flask_more_smorest.utils import (
    check_password_hash,
    convert_snake_to_camel,
    generate_password_hash,
    validate_password_length,
)


class TestConvertSnakeToCamel:
    """Tests for convert_snake_to_camel function."""

    def test_simple_word(self) -> None:
        """Test conversion of simple words without underscores."""
        assert convert_snake_to_camel("user") == "user"
        assert convert_snake_to_camel("product") == "product"

    def test_snake_case_conversion(self) -> None:
        """Test conversion of snake_case strings."""
        assert convert_snake_to_camel("user_profile") == "UserProfile"
        assert convert_snake_to_camel("product_category") == "ProductCategory"
        assert convert_snake_to_camel("order_item_detail") == "OrderItemDetail"

    def test_multiple_underscores(self) -> None:
        """Test conversion with multiple consecutive underscores."""
        assert convert_snake_to_camel("user__profile") == "User_Profile"
        assert convert_snake_to_camel("test___case") == "Test__Case"

    def test_leading_trailing_underscores(self) -> None:
        """Test conversion with leading or trailing underscores."""
        assert convert_snake_to_camel("_user") == "_User"
        assert convert_snake_to_camel("user_") == "User_"
        assert convert_snake_to_camel("_user_profile_") == "_UserProfile_"

    def test_empty_string(self) -> None:
        """Test conversion of empty string."""
        assert convert_snake_to_camel("") == ""

    def test_single_underscore(self) -> None:
        """Test conversion of single underscore."""
        assert convert_snake_to_camel("_") == "__"

    def test_mixed_case_input(self) -> None:
        """Test conversion with mixed case input."""
        assert convert_snake_to_camel("User_Profile") == "UserProfile"
        assert convert_snake_to_camel("user_Profile") == "UserProfile"

    def test_numeric_values(self) -> None:
        """Test conversion with numeric values."""
        assert convert_snake_to_camel("user_123") == "User123"
        assert convert_snake_to_camel("test_1_2_3") == "Test123"

    def test_all_caps(self) -> None:
        """Test conversion of all caps strings."""
        assert convert_snake_to_camel("USER") == "USER"
        assert convert_snake_to_camel("USER_PROFILE") == "UserProfile"


class TestBaseModelSession:
    """Tests for BaseModel session handling."""

    def test_base_model_allows_inactive_session(self, app: Flask) -> None:
        """Test that BaseModel can create instances when session is closed."""

        class SimpleModel(BaseModel):
            name: Mapped[str] = mapped_column(sa.String(50))

        with app.app_context():
            db.create_all()

            instance = SimpleModel(name="first")
            instance.save()
            db.session.commit()
            db.session.close()

            # Session is closed (inactive). New instances should still be creatable.
            other = SimpleModel(name="second")
            assert other.name == "second"


class TestSchemaPreload:
    """Tests for BaseSchema preload functionality."""

    def test_preload_injects_view_args(self) -> None:
        """Test that preload injects view_args into schema data."""

        class DummySchema(BaseSchema):
            resource_id = fields.String()

        schema = DummySchema()
        app = Flask(__name__)
        app.config["TESTING"] = True

        with app.test_request_context("/resource/123") as ctx:
            ctx.request.view_args = {"resource_id": "123"}
            data = schema.pre_load({}, view_args={}, unknown=None)
            assert data["resource_id"] == "123"


class TestValidatePasswordLength:
    """Tests for validate_password_length and the bcrypt guard."""

    def test_73_byte_ascii_raises(self) -> None:
        """A 73-byte ASCII password raises ValidationError."""
        with pytest.raises(ValidationError, match="72 bytes"):
            validate_password_length("a" * 73)

    def test_72_byte_ascii_passes(self) -> None:
        """A 72-byte ASCII password passes."""
        validate_password_length("a" * 72)  # no exception

    def test_72_byte_multibyte_passes(self) -> None:
        """24 characters each 3 bytes (72 bytes total) passes."""
        # U+4E2D is 3 bytes in UTF-8
        validate_password_length("\u4e2d" * 24)  # no exception

    def test_73_byte_multibyte_raises(self) -> None:
        """25 characters each 3 bytes (75 bytes) raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_password_length("\u4e2d" * 25)

    def test_check_password_hash_long_password_returns_false(self) -> None:
        """A >72-byte password is rejected even when its first 72 bytes match the hash."""
        valid_hash = generate_password_hash("a" * 72)
        assert check_password_hash("a" * 72, valid_hash) is True
        assert check_password_hash("a" * 73, valid_hash) is False
