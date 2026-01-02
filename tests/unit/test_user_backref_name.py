"""Tests for HasUserMixin backref name configuration."""

from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest.perms.model_mixins import HasUserMixin
from flask_more_smorest.sqla import BaseModel, db


def test_default_backref_name(app: Flask) -> None:
    """Test that default backref name is auto-generated from tablename."""

    class TestModelDefault(HasUserMixin, BaseModel):
        title: Mapped[str] = mapped_column(db.String(100))

    # Should auto-generate as "test_model_defaults" (plural of tablename)
    assert TestModelDefault._user_backref_name() == "test_model_defaults"


def test_custom_backref_name(app: Flask) -> None:
    """Test that custom backref name is used when specified."""

    class TestModelCustom(HasUserMixin, BaseModel):
        __user_backref_name__ = "my_items"
        title: Mapped[str] = mapped_column(db.String(100))

    assert TestModelCustom._user_backref_name() == "my_items"


def test_empty_string_backref_name(app: Flask) -> None:
    """Test that empty string disables backref."""

    class TestModelEmptyBackref(HasUserMixin, BaseModel):
        __user_backref_name__ = ""
        title: Mapped[str] = mapped_column(db.String(100))

    assert TestModelEmptyBackref._user_backref_name() == ""


def test_none_backref_name(app: Flask) -> None:
    """Test that None uses default auto-generation."""

    class TestModelNone(HasUserMixin, BaseModel):
        __user_backref_name__ = None
        title: Mapped[str] = mapped_column(db.String(100))

    # Should auto-generate when None
    assert TestModelNone._user_backref_name() == "test_model_nones"


def test_backref_with_custom_field_names(app: Flask) -> None:
    """Test backref name with custom field and relationship names."""

    class TestModelFields(HasUserMixin, BaseModel):
        __user_field_name__ = "author_id"
        __user_relationship_name__ = "author"
        __user_backref_name__ = "articles"
        title: Mapped[str] = mapped_column(db.String(100))

    assert TestModelFields._user_backref_name() == "articles"
    assert TestModelFields._user_field_alias() == "author_id"
    assert TestModelFields._user_relationship_alias() == "author"
