"""Tests for CRUDBlueprint methods and skip_methods logic."""

import warnings

import pytest

from flask_more_smorest.crud.crud_blueprint import CRUDBlueprint, CRUDMethod
from flask_more_smorest.sqla.base_model import BaseModel


def test_methods_list_mode_whitelist(app):
    """Test that list mode only enables specified methods."""

    class TestModel(BaseModel):
        __tablename__ = "test_list_mode"

    bp = CRUDBlueprint(
        "test_list",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods=[CRUDMethod.INDEX, CRUDMethod.GET],
    )

    # Check that only INDEX and GET are enabled
    assert (
        CRUDMethod.INDEX
        in bp._build_config(
            "test_list",
            __name__,
            TestModel,
            TestModel.Schema,
            None,
            None,
            "id",
            None,
            [CRUDMethod.INDEX, CRUDMethod.GET],
            None,
            None,
        ).methods
    )
    assert (
        CRUDMethod.GET
        in bp._build_config(
            "test_list",
            __name__,
            TestModel,
            TestModel.Schema,
            None,
            None,
            "id",
            None,
            [CRUDMethod.INDEX, CRUDMethod.GET],
            None,
            None,
        ).methods
    )

    config = bp._build_config(
        "test_list",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        [CRUDMethod.INDEX, CRUDMethod.GET],
        None,
        None,
    )

    assert len(config.methods) == 2
    assert CRUDMethod.INDEX in config.methods
    assert CRUDMethod.GET in config.methods
    assert CRUDMethod.POST not in config.methods
    assert CRUDMethod.PATCH not in config.methods
    assert CRUDMethod.DELETE not in config.methods


def test_methods_dict_mode_all_enabled_by_default(app):
    """Test that dict mode enables all methods by default."""

    class TestModel(BaseModel):
        __tablename__ = "test_dict_mode"

    config = CRUDBlueprint(
        "test_dict",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods={
            CRUDMethod.POST: {"schema": TestModel.Schema},
        },
    )._build_config(
        "test_dict",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        {CRUDMethod.POST: {"schema": TestModel.Schema}},
        None,
        None,
    )

    # All methods should be enabled since we used dict mode
    assert len(config.methods) == len(CRUDMethod)
    assert CRUDMethod.INDEX in config.methods
    assert CRUDMethod.GET in config.methods
    assert CRUDMethod.POST in config.methods
    assert CRUDMethod.PATCH in config.methods
    assert CRUDMethod.DELETE in config.methods

    # POST should have custom config
    assert config.methods[CRUDMethod.POST].get("schema") == TestModel.Schema


def test_methods_dict_mode_with_false_disables(app):
    """Test that False in dict mode disables methods."""

    class TestModel(BaseModel):
        __tablename__ = "test_dict_false"

    config = CRUDBlueprint(
        "test_dict_false",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods={
            CRUDMethod.PATCH: False,
            CRUDMethod.DELETE: False,
        },
    )._build_config(
        "test_dict_false",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        {CRUDMethod.PATCH: False, CRUDMethod.DELETE: False},
        None,
        None,
    )

    # Should have all methods except PATCH and DELETE
    assert len(config.methods) == 3
    assert CRUDMethod.INDEX in config.methods
    assert CRUDMethod.GET in config.methods
    assert CRUDMethod.POST in config.methods
    assert CRUDMethod.PATCH not in config.methods
    assert CRUDMethod.DELETE not in config.methods


def test_skip_methods_removes_after_normalization(app):
    """Test that skip_methods removes methods after normalization."""

    class TestModel(BaseModel):
        __tablename__ = "test_skip"

    config = CRUDBlueprint(
        "test_skip",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        skip_methods=[CRUDMethod.PATCH, CRUDMethod.DELETE],
    )._build_config(
        "test_skip",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        list(CRUDMethod),  # Default: all methods
        [CRUDMethod.PATCH, CRUDMethod.DELETE],
        None,
    )

    # Should have all methods except PATCH and DELETE
    assert len(config.methods) == 3
    assert CRUDMethod.INDEX in config.methods
    assert CRUDMethod.GET in config.methods
    assert CRUDMethod.POST in config.methods
    assert CRUDMethod.PATCH not in config.methods
    assert CRUDMethod.DELETE not in config.methods


def test_skip_methods_with_list_mode(app):
    """Test skip_methods can further limit list mode."""

    class TestModel(BaseModel):
        __tablename__ = "test_skip_list"

    config = CRUDBlueprint(
        "test_skip_list",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods=[CRUDMethod.INDEX, CRUDMethod.GET, CRUDMethod.POST],
        skip_methods=[CRUDMethod.POST],
    )._build_config(
        "test_skip_list",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        [CRUDMethod.INDEX, CRUDMethod.GET, CRUDMethod.POST],
        [CRUDMethod.POST],
        None,
    )

    # Should have INDEX and GET only (POST skipped)
    assert len(config.methods) == 2
    assert CRUDMethod.INDEX in config.methods
    assert CRUDMethod.GET in config.methods
    assert CRUDMethod.POST not in config.methods


def test_redundant_skip_methods_warns(app):
    """Test that redundant skip_methods usage triggers a warning."""

    class TestModel(BaseModel):
        __tablename__ = "test_warn"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Just call _build_config directly, don't instantiate the blueprint twice
        bp = CRUDBlueprint(
            "test_warn_dummy",
            __name__,
            model=TestModel,
            schema=TestModel.Schema,
        )

        bp._build_config(
            "test_warn",
            __name__,
            TestModel,
            TestModel.Schema,
            None,
            None,
            "id",
            None,
            {CRUDMethod.PATCH: False},
            [CRUDMethod.PATCH],
            None,
        )

        # Should have triggered a warning about redundancy
        # Filter for just our warning (ignore JWT warnings etc)
        redundant_warnings = [warning for warning in w if "redundant" in str(warning.message).lower()]
        assert len(redundant_warnings) == 1
        assert "PATCH" in str(redundant_warnings[0].message)


def test_methods_dict_with_true_value(app):
    """Test that True values in dict mode work correctly."""

    class TestModel(BaseModel):
        __tablename__ = "test_true"

    config = CRUDBlueprint(
        "test_true",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods={
            CRUDMethod.INDEX: True,  # Explicitly enabled
            CRUDMethod.POST: True,
        },
    )._build_config(
        "test_true",
        __name__,
        TestModel,
        TestModel.Schema,
        None,
        None,
        "id",
        None,
        {CRUDMethod.INDEX: True, CRUDMethod.POST: True},
        None,
        None,
    )

    # All methods should still be enabled (dict mode default)
    assert len(config.methods) == len(CRUDMethod)
    assert all(method in config.methods for method in CRUDMethod)


def test_methods_dict_invalid_value_raises(app):
    """Test that invalid dict values raise TypeError."""

    class TestModel(BaseModel):
        __tablename__ = "test_invalid"

    bp = CRUDBlueprint(
        "test_invalid",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
    )

    with pytest.raises(TypeError, match="must be a dict, True, or False"):
        bp._normalize_methods({CRUDMethod.INDEX: "invalid"})


def test_methods_invalid_type_raises(app):
    """Test that invalid methods parameter type raises TypeError."""

    class TestModel(BaseModel):
        __tablename__ = "test_invalid_type"

    bp = CRUDBlueprint(
        "test_invalid_type",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
    )

    with pytest.raises(TypeError, match="must be a list or a dict"):
        bp._normalize_methods("invalid")


def test_empty_methods_list(app):
    """Test that empty methods list creates no routes."""

    class TestModel(BaseModel):
        __tablename__ = "test_empty"

    config = CRUDBlueprint(
        "test_empty",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods=[],
    )._build_config("test_empty", __name__, TestModel, TestModel.Schema, None, None, "id", None, [], None, None)

    assert len(config.methods) == 0


def test_empty_methods_dict(app):
    """Test that empty methods dict enables all by default."""

    class TestModel(BaseModel):
        __tablename__ = "test_empty_dict"

    config = CRUDBlueprint(
        "test_empty_dict",
        __name__,
        model=TestModel,
        schema=TestModel.Schema,
        methods={},
    )._build_config("test_empty_dict", __name__, TestModel, TestModel.Schema, None, None, "id", None, {}, None, None)

    # Empty dict should enable all methods (dict mode behavior)
    assert len(config.methods) == len(CRUDMethod)
