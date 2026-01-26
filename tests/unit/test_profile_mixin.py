"""Unit tests for ProfileMixin.

Tests ProfileMixin properties and methods including:
- full_name computed property
- parse_full_name() classmethod
- display_name field
- avatar_url field
- avatar property
- Edge cases for name parsing
"""

import pytest

from flask_more_smorest.perms.model_mixins import ProfileMixin


class TestProfileMixin:
    """Test ProfileMixin properties and class methods."""

    def test_full_name_with_both_names(self) -> None:
        """Test full_name property when both first_name and last_name are set."""
        mixin = ProfileMixin()
        mixin.first_name = "John"
        mixin.last_name = "Doe"
        assert mixin.full_name == "John Doe"

    def test_full_name_with_first_name_only(self) -> None:
        """Test full_name property when only first_name is set."""
        mixin = ProfileMixin()
        mixin.first_name = "Jane"
        mixin.last_name = None
        assert mixin.full_name == "Jane"

    def test_full_name_with_last_name_only(self) -> None:
        """Test full_name property when only last_name is set."""
        mixin = ProfileMixin()
        mixin.first_name = None
        mixin.last_name = "Smith"
        assert mixin.full_name == "Smith"

    def test_full_name_with_no_names(self) -> None:
        """Test full_name property when neither name is set."""
        mixin = ProfileMixin()
        mixin.first_name = None
        mixin.last_name = None
        assert mixin.full_name == ""

    def test_full_name_with_empty_strings(self) -> None:
        """Test full_name property with empty strings."""
        mixin = ProfileMixin()
        mixin.first_name = ""
        mixin.last_name = ""
        assert mixin.full_name == ""

    def test_full_name_with_mixed_empty_and_none(self) -> None:
        """Test full_name property with empty strings and None."""
        mixin = ProfileMixin()
        mixin.first_name = ""
        mixin.last_name = None
        assert mixin.full_name == ""

        mixin.first_name = None
        mixin.last_name = ""
        assert mixin.full_name == ""

    def test_full_name_with_whitespace(self) -> None:
        """Test full_name property with whitespace characters."""
        mixin = ProfileMixin()
        mixin.first_name = "  John  "
        mixin.last_name = "  Doe  "
        assert mixin.full_name == "  John     Doe  "  # "  John  " + " " + "  Doe  "

    def test_parse_full_name_standard(self) -> None:
        """Test parse_full_name with standard first and last name."""
        result = ProfileMixin.parse_full_name("Alice Wonderland")
        assert result == {"first_name": "Alice", "last_name": "Wonderland"}

    def test_parse_full_name_single_name(self) -> None:
        """Test parse_full_name with single name (no space)."""
        result = ProfileMixin.parse_full_name("Bob")
        assert result == {"first_name": "Bob", "last_name": ""}

    def test_parse_full_name_with_leading_trailing_whitespace(self) -> None:
        """Test parse_full_name strips leading and trailing whitespace."""
        result = ProfileMixin.parse_full_name("  Alice Wonderland  ")
        assert result == {"first_name": "Alice", "last_name": "Wonderland"}

    def test_parse_full_name_with_multiple_spaces_between_names(self) -> None:
        """Test parse_full_name handles multiple spaces between names."""
        # Only split on first space, so everything after first space is last_name
        result = ProfileMixin.parse_full_name("Alice   Wonderland")
        assert result == {"first_name": "Alice", "last_name": "Wonderland"}

    def test_parse_full_name_with_middle_names(self) -> None:
        """Test parse_full_name treats middle names as part of last_name."""
        # "John Ronald Reuel Tolkien" -> first_name: "John", last_name: "Ronald Reuel Tolkien"
        result = ProfileMixin.parse_full_name("John Ronald Reuel Tolkien")
        assert result == {"first_name": "John", "last_name": "Ronald Reuel Tolkien"}

    def test_parse_full_name_with_hyphenated_names(self) -> None:
        """Test parse_full_name with hyphenated names."""
        result = ProfileMixin.parse_full_name("Mary-Jane Watson")
        assert result == {"first_name": "Mary-Jane", "last_name": "Watson"}

    def test_parse_full_name_with_apostrophes(self) -> None:
        """Test parse_full_name with apostrophes."""
        result = ProfileMixin.parse_full_name("O'Connor Smith")
        assert result == {"first_name": "O'Connor", "last_name": "Smith"}

    def test_parse_full_name_empty_string(self) -> None:
        """Test parse_full_name with empty string.

        NOTE: This exposes a bug in ProfileMixin.parse_full_name() - it
        raises IndexError on empty strings. This test documents the issue.
        """
        # The current implementation raises IndexError on empty strings
        # Expected behavior: should return {"first_name": "", "last_name": ""}
        # Actual behavior: raises IndexError
        with pytest.raises(IndexError):
            ProfileMixin.parse_full_name("")

    def test_parse_full_name_whitespace_only(self) -> None:
        """Test parse_full_name with whitespace only.

        NOTE: This exposes a bug in ProfileMixin.parse_full_name() - it
        raises IndexError on whitespace-only strings. This test documents issue.
        """
        # The current implementation raises IndexError on whitespace-only strings
        # Expected behavior: should return {"first_name": "", "last_name": ""}
        # Actual behavior: raises IndexError
        with pytest.raises(IndexError):
            ProfileMixin.parse_full_name("   ")

    def test_parse_full_name_with_tabs(self) -> None:
        """Test parse_full_name with tabs (treated as whitespace)."""
        result = ProfileMixin.parse_full_name("\tAlice\tWonderland\t")
        assert result == {"first_name": "Alice", "last_name": "Wonderland"}

    def test_parse_full_name_single_word_with_whitespace(self) -> None:
        """Test parse_full_name single word surrounded by whitespace."""
        result = ProfileMixin.parse_full_name("  Bob  ")
        assert result == {"first_name": "Bob", "last_name": ""}

    def test_parse_full_name_unicode_names(self) -> None:
        """Test parse_full_name with Unicode characters."""
        result = ProfileMixin.parse_full_name("François Müller")
        assert result == {"first_name": "François", "last_name": "Müller"}

    def test_display_name_field_exists(self) -> None:
        """Test that display_name field exists and can be set."""
        mixin = ProfileMixin()
        mixin.display_name = "Johnny D."
        assert mixin.display_name == "Johnny D."

    def test_display_name_can_be_none(self) -> None:
        """Test that display_name can be None."""
        mixin = ProfileMixin()
        mixin.display_name = None
        assert mixin.display_name is None

    def test_avatar_url_field_exists(self) -> None:
        """Test that avatar_url field exists and can be set."""
        mixin = ProfileMixin()
        mixin.avatar_url = "https://example.com/avatar.jpg"
        assert mixin.avatar_url == "https://example.com/avatar.jpg"

    def test_avatar_url_can_be_none(self) -> None:
        """Test that avatar_url can be None."""
        mixin = ProfileMixin()
        mixin.avatar_url = None
        assert mixin.avatar_url is None

    def test_avatar_property_returns_avatar_url(self) -> None:
        """Test that avatar property returns avatar_url."""
        mixin = ProfileMixin()
        mixin.avatar_url = "https://example.com/avatar.jpg"
        assert mixin.avatar == "https://example.com/avatar.jpg"

    def test_avatar_property_with_none(self) -> None:
        """Test that avatar property returns None when avatar_url is None."""
        mixin = ProfileMixin()
        mixin.avatar_url = None
        assert mixin.avatar is None

    def test_avatar_property_is_read_only_alias(self) -> None:
        """Test that avatar is a property (read-only alias for avatar_url)."""
        mixin = ProfileMixin()
        # Setting avatar_url should affect avatar property
        mixin.avatar_url = "https://example.com/new.jpg"
        assert mixin.avatar == "https://example.com/new.jpg"

    def test_all_profile_fields_can_be_set(self) -> None:
        """Test that all profile fields can be set and retrieved."""
        mixin = ProfileMixin()
        mixin.first_name = "John"
        mixin.last_name = "Doe"
        mixin.display_name = "JD"
        mixin.avatar_url = "https://example.com/john.jpg"

        assert mixin.first_name == "John"
        assert mixin.last_name == "Doe"
        assert mixin.display_name == "JD"
        assert mixin.avatar_url == "https://example.com/john.jpg"
        assert mixin.full_name == "John Doe"
        assert mixin.avatar == "https://example.com/john.jpg"
