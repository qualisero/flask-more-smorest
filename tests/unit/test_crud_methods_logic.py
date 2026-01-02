"""Tests for CRUDBlueprint methods and skip_methods logic."""

import warnings

import pytest
from flask import Flask

from flask_more_smorest.crud.crud_blueprint import CRUDBlueprint, CRUDMethod
from flask_more_smorest.sqla.base_model import BaseModel


def test_methods_list_mode_whitelist(app: Flask) -> None:
    """Test that list mode only enables specified methods."""

    class TestModelListMode(BaseModel):
        pass

    bp = CRUDBlueprint(
        "test_list",
        __name__,
        model=TestModelListMode,
        schema=TestModelListMode.Schema,
        methods=[CRUDMethod.INDEX, CRUDMethod.GET],
    )

    # Check that only INDEX and GET are enabled
    assert (
        CRUDMethod.INDEX
        in bp._build_config(
            "test_list",
            __name__,
            TestModelListMode,
            TestModelListMode.Schema,
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
            TestModelListMode,
            TestModelListMode.Schema,
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
        TestModelListMode,
        TestModelListMode.Schema,
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


def test_methods_dict_mode_all_enabled_by_default(app: Flask) -> None:
    """Test that dict mode enables all methods by default."""

    class TestModelDictMode(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_dict",
        __name__,
        model=TestModelDictMode,
        schema=TestModelDictMode.Schema,
        methods={
            CRUDMethod.POST: {"schema": TestModelDictMode.Schema},
        },
    )._build_config(
        "test_dict",
        __name__,
        TestModelDictMode,
        TestModelDictMode.Schema,
        None,
        None,
        "id",
        None,
        {CRUDMethod.POST: {"schema": TestModelDictMode.Schema}},
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
    assert config.methods[CRUDMethod.POST].get("schema") == TestModelDictMode.Schema


def test_methods_dict_mode_with_false_disables(app: Flask) -> None:
    """Test that False in dict mode disables methods."""

    class TestModelDictFalse(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_dict_false",
        __name__,
        model=TestModelDictFalse,
        schema=TestModelDictFalse.Schema,
        methods={
            CRUDMethod.PATCH: False,
            CRUDMethod.DELETE: False,
        },
    )._build_config(
        "test_dict_false",
        __name__,
        TestModelDictFalse,
        TestModelDictFalse.Schema,
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


def test_skip_methods_removes_after_normalization(app: Flask) -> None:
    """Test that skip_methods removes methods after normalization."""

    class TestModelSkip(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_skip",
        __name__,
        model=TestModelSkip,
        schema=TestModelSkip.Schema,
        skip_methods=[CRUDMethod.PATCH, CRUDMethod.DELETE],
    )._build_config(
        "test_skip",
        __name__,
        TestModelSkip,
        TestModelSkip.Schema,
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


def test_skip_methods_with_list_mode(app: Flask) -> None:
    """Test skip_methods can further limit list mode."""

    class TestModelSkipList(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_skip_list",
        __name__,
        model=TestModelSkipList,
        schema=TestModelSkipList.Schema,
        methods=[CRUDMethod.INDEX, CRUDMethod.GET, CRUDMethod.POST],
        skip_methods=[CRUDMethod.POST],
    )._build_config(
        "test_skip_list",
        __name__,
        TestModelSkipList,
        TestModelSkipList.Schema,
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


def test_redundant_skip_methods_warns(app: Flask) -> None:
    """Test that redundant skip_methods usage triggers a warning."""

    class TestModelWarn(BaseModel):
        pass

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Just call _build_config directly, don't instantiate the blueprint twice
        bp = CRUDBlueprint(
            "test_warn_dummy",
            __name__,
            model=TestModelWarn,
            schema=TestModelWarn.Schema,
        )

        bp._build_config(
            "test_warn",
            __name__,
            TestModelWarn,
            TestModelWarn.Schema,
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


def test_methods_dict_with_true_value(app: Flask) -> None:
    """Test that True values in dict mode work correctly."""

    class TestModelTrue(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_true",
        __name__,
        model=TestModelTrue,
        schema=TestModelTrue.Schema,
        methods={
            CRUDMethod.INDEX: True,  # Explicitly enabled
            CRUDMethod.POST: True,
        },
    )._build_config(
        "test_true",
        __name__,
        TestModelTrue,
        TestModelTrue.Schema,
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


def test_methods_dict_invalid_value_raises(app: Flask) -> None:
    """Test that invalid dict values raise TypeError."""

    class TestModelInvalid(BaseModel):
        pass

    bp = CRUDBlueprint(
        "test_invalid",
        __name__,
        model=TestModelInvalid,
        schema=TestModelInvalid.Schema,
    )

    with pytest.raises(TypeError, match="must be a dict, True, or False"):
        bp._normalize_methods({CRUDMethod.INDEX: "invalid"})  # type: ignore[dict-item]


def test_methods_invalid_type_raises(app: Flask) -> None:
    """Test that invalid methods parameter type raises TypeError."""

    class TestModelInvalidType(BaseModel):
        pass

    bp = CRUDBlueprint(
        "test_invalid_type",
        __name__,
        model=TestModelInvalidType,
        schema=TestModelInvalidType.Schema,
    )

    with pytest.raises(TypeError, match="must be a list or a dict"):
        bp._normalize_methods("invalid")  # type: ignore[arg-type]


def test_empty_methods_list(app: Flask) -> None:
    """Test that empty methods list creates no routes."""

    class TestModelEmpty(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_empty",
        __name__,
        model=TestModelEmpty,
        schema=TestModelEmpty.Schema,
        methods=[],
    )._build_config(
        "test_empty", __name__, TestModelEmpty, TestModelEmpty.Schema, None, None, "id", None, [], None, None
    )

    assert len(config.methods) == 0


def test_empty_methods_dict(app: Flask) -> None:
    """Test that empty methods dict enables all by default."""

    class TestModelEmptyDict(BaseModel):
        pass

    config = CRUDBlueprint(
        "test_empty_dict",
        __name__,
        model=TestModelEmptyDict,
        schema=TestModelEmptyDict.Schema,
        methods={},
    )._build_config(
        "test_empty_dict",
        __name__,
        TestModelEmptyDict,
        TestModelEmptyDict.Schema,
        None,
        None,
        "id",
        None,
        {},
        None,
        None,
    )

    # Empty dict should enable all methods (dict mode behavior)
    assert len(config.methods) == len(CRUDMethod)
