"""Tests for utility functions."""

from flask_more_smorest.utils import convert_snake_to_camel


class TestConvertSnakeToCamel:
    """Tests for convert_snake_to_camel function."""

    def test_simple_word(self):
        """Test conversion of simple words without underscores."""
        assert convert_snake_to_camel("user") == "user"
        assert convert_snake_to_camel("product") == "product"

    def test_snake_case_conversion(self):
        """Test conversion of snake_case strings."""
        assert convert_snake_to_camel("user_profile") == "UserProfile"
        assert convert_snake_to_camel("product_category") == "ProductCategory"
        assert convert_snake_to_camel("order_item_detail") == "OrderItemDetail"

    def test_multiple_underscores(self):
        """Test conversion with multiple consecutive underscores."""
        assert convert_snake_to_camel("user__profile") == "User_Profile"
        assert convert_snake_to_camel("test___case") == "Test__Case"

    def test_leading_trailing_underscores(self):
        """Test conversion with leading or trailing underscores."""
        assert convert_snake_to_camel("_user") == "_User"
        assert convert_snake_to_camel("user_") == "User_"
        assert convert_snake_to_camel("_user_profile_") == "_UserProfile_"

    def test_empty_string(self):
        """Test conversion of empty string."""
        assert convert_snake_to_camel("") == ""

    def test_single_underscore(self):
        """Test conversion of single underscore."""
        assert convert_snake_to_camel("_") == "__"  # Expected behavior based on implementation

    def test_mixed_case_input(self):
        """Test conversion with mixed case input."""
        assert convert_snake_to_camel("User_Profile") == "UserProfile"
        assert convert_snake_to_camel("user_Profile") == "UserProfile"
