"""Unit tests for utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import Flask
from marshmallow import fields
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import BaseModel, BaseSchema, db
from flask_more_smorest.utils import convert_snake_to_camel

if TYPE_CHECKING:  # pragma: no cover
    pass


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
