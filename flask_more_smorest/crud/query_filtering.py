"""Query filtering utilities for Flask-Smorest CRUD operations.

This module provides utilities for generating filter schemas and converting
filter parameters into SQLAlchemy query statements. It supports:
- Range queries for date/datetime fields (field__from, field__to)
- Min/max queries for numeric fields (field__min, field__max)
- Enum list filters (field__in)
"""

import copy
from collections.abc import Mapping
from typing import Any

import marshmallow as ma
from marshmallow import validate
from sqlalchemy import ColumnElement, inspect, or_

from flask_more_smorest.sqla.base_model import BaseModel

# Filter suffixes used for range and comparison queries
_FILTER_SUFFIXES = ("__from", "__to", "__min", "__max", "__in")

_NUMERIC_FIELDS = (ma.fields.Integer, ma.fields.Float, ma.fields.Decimal)
_TEMPORAL_FIELDS = (ma.fields.DateTime, ma.fields.Date)


def _clone_field(field: ma.fields.Field) -> ma.fields.Field:
    new_field = copy.deepcopy(field)
    new_field.load_default = None
    new_field.load_only = True
    new_field.dump_only = False
    new_field.required = False
    # Write-schema validators (Regexp, Length, Range, custom callables) must not
    # apply to filter parameters: filters compare against *stored* values, and
    # rows may legitimately predate the current write-time validation rules.
    # Filtering by an arbitrary value is always safe — it simply matches
    # nothing. Type coercion (the field class itself) still applies.
    new_field.validators = []
    return new_field


def generate_filter_schema(base_schema: type[ma.Schema] | ma.Schema) -> type[ma.Schema]:
    """Generate a filtering schema from a base schema.

    This function creates a new schema class that can be used for filtering
    queries. It automatically converts certain field types to filter-friendly
    variants:
    - Date/DateTime fields become range filters with __from and __to suffixes
    - Numeric fields get __min and __max filters (equality removed for floats)
    - Enum fields get __in list filters
    - Adds optional pagination parameters (page, page_size) to allow validation

    Args:
        base_schema: The base Marshmallow schema class to derive filters from

    Returns:
        A new schema class suitable for filtering operations with all fields
        made optional and set to load_only

    Example:
        >>> class UserSchema(Schema):
        ...     name = fields.String()
        ...     age = fields.Integer()
        ...     created_at = fields.DateTime()
        >>> FilterSchema = generate_filter_schema(UserSchema)
        >>> # FilterSchema will have: name, age, age__min, age__max,
        >>> # created_at__from, created_at__to
    """

    if isinstance(base_schema, ma.Schema):
        base_instance = base_schema
        base_cls = type(base_instance)
    else:
        base_cls = base_schema
        base_instance = base_cls()

    field_definitions: dict[str, ma.fields.Field] = {}
    preserved_fields: dict[str, ma.fields.Field] = {}

    for field_name, field_obj in base_instance.fields.items():
        new_fields: dict[str, ma.fields.Field] = {}
        keep_original = True

        if isinstance(field_obj, _TEMPORAL_FIELDS):
            keep_original = False
            for suffix in ("__from", "__to"):
                cloned = _clone_field(field_obj)
                new_fields[f"{field_name}{suffix}"] = cloned

        if isinstance(field_obj, _NUMERIC_FIELDS):
            for suffix in ("__min", "__max"):
                cloned = _clone_field(field_obj)
                new_fields[f"{field_name}{suffix}"] = cloned
            if not isinstance(field_obj, ma.fields.Integer):
                keep_original = False

        if isinstance(field_obj, ma.fields.Enum):
            enum_field = ma.fields.List(
                ma.fields.Enum(field_obj.enum),
                load_default=None,
                load_only=True,
                dump_only=False,
                required=False,
            )
            new_fields[f"{field_name}__in"] = enum_field

        if keep_original:
            preserved_fields[field_name] = _clone_field(field_obj)

        for new_name, new_field in new_fields.items():
            field_definitions[new_name] = new_field

    def _remove_none_fields(self: ma.Schema, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {k: v for k, v in data.items() if v is not None}

    # Control parameters have their own load_default values and must not be
    # reset by the generic _on_bind_field hook that normalises schema fields.
    _CONTROL_FIELDS = frozenset({"page", "page_size", "nulls_match"})

    def _on_bind_field(self: ma.Schema, field_name: str, field_obj: ma.fields.Field) -> None:
        if field_name in _CONTROL_FIELDS:
            return
        field_obj.load_default = None
        field_obj.load_only = True
        field_obj.dump_only = False
        field_obj.required = False

    base_meta = getattr(base_cls, "Meta", object)

    meta_attrs: dict[str, object] = {
        "partial": True,
        "load_instance": False,
        "unknown": ma.RAISE,
        # The filter schema declares its own field set: the preserved originals,
        # the derived __min/__max/__from/__to/__in variants and the
        # page/page_size/nulls_match control params. `fields`, `additional` and
        # `exclude` are inherited from the RESPONSE schema's Meta, where they
        # describe what to serialise; applied here they silently drop the control
        # params (a response `Meta.fields` allowlist made `page_size` return 422
        # and capped lists at the default page). State the filter schema's own
        # set explicitly instead.
        "fields": tuple(preserved_fields) + tuple(field_definitions) + ("page", "page_size", "nulls_match"),
        "additional": (),
        "exclude": (),
    }

    meta_class = type(
        "Meta",
        (base_meta,),
        meta_attrs,
    )

    attrs: dict[str, object] = {
        "Meta": meta_class,
        "on_bind_field": _on_bind_field,
        "remove_none_fields": ma.post_load(_remove_none_fields),
    }
    attrs.update(preserved_fields)
    attrs.update(field_definitions)

    # Pagination parameters
    attrs["page"] = ma.fields.Integer(
        load_default=None,
        load_only=True,
        required=False,
        validate=validate.Range(min=1),
    )
    attrs["page_size"] = ma.fields.Integer(
        load_default=None,
        load_only=True,
        required=False,
        validate=validate.Range(min=0),
    )
    # When nulls_match=true, every produced filter condition is widened to
    # (condition OR model_field IS NULL) — "null in local data counts as a match".
    attrs["nulls_match"] = ma.fields.Boolean(
        load_default=False,
        load_only=True,
        required=False,
    )

    class_name = f"{base_cls.__name__}FilterSchema"
    FilterSchema: type[ma.Schema] = type(class_name, (base_cls,), attrs)
    return FilterSchema


def _extract_base_field_name(field_name: str) -> str:
    """Extract the base field name by removing filter suffixes.

    Args:
        field_name: Field name possibly containing a filter suffix

    Returns:
        Base field name with suffix removed
    """
    for suffix in _FILTER_SUFFIXES:
        if field_name.endswith(suffix):
            return field_name[: -len(suffix)]
    return field_name


def _validate_filter_field(field_name: str, model: type[BaseModel], valid_columns: set[str]) -> str:
    """Validate that a filter field exists on the model.

    Args:
        field_name: The filter field name (may include suffix)
        model: The SQLAlchemy model class
        valid_columns: Set of valid column names on the model

    Returns:
        The base field name (without suffix)

    Raises:
        ValueError: If the base field does not exist on the model
    """
    base_field = _extract_base_field_name(field_name)

    if base_field not in valid_columns:
        raise ValueError(
            f"Invalid filter field '{base_field}' for model {model.__name__}. "
            f"Valid fields are: {', '.join(sorted(valid_columns))}"
        )

    return base_field


def get_statements_from_filters(kwargs: Mapping[str, Any], model: type[BaseModel]) -> set[ColumnElement[bool]]:
    """Convert query kwargs into SQLAlchemy filters based on the schema.

    This function processes filtering parameters and converts them to
    SQLAlchemy WHERE clause conditions, supporting:
    - Range queries: field__from (>=) and field__to (<=)
    - Numeric ranges: field__min (>=) and field__max (<=)
    - Exact equality: field = value

    All filter field names are validated against the model's columns to
    prevent access to private attributes or non-existent fields.

    Args:
        kwargs: Dictionary of filter parameters from the query string
        model: SQLAlchemy model class to filter on

    Returns:
        Set of SQLAlchemy filter conditions (BinaryExpression objects)

    Raises:
        ValueError: If a filter field does not exist on the model

    Example:
        >>> filters = {'age__min': 18, 'age__max': 65, 'is_active': True}
        >>> stmts = get_statements_from_filters(filters, User)
        >>> results = User.query.filter(*stmts).all()
    """
    filters: set[ColumnElement[bool]] = set()

    # Pop control parameters before the filter loop so they are never
    # treated as column references.
    kwargs = dict(kwargs)
    nulls_match = bool(kwargs.pop("nulls_match", False))

    # Get valid column names from the model for validation
    valid_columns = {col.name for col in inspect(model).columns}

    for field_name, value in kwargs.items():
        if value is None:
            continue
        if field_name in ("page", "page_size"):
            # Skip pagination parameters as they are handled separately
            continue

        # Validate the field exists on the model
        base_field_name = _validate_filter_field(field_name, model, valid_columns)
        model_field = getattr(model, base_field_name)

        if field_name.endswith("__from"):
            condition: ColumnElement[bool] = model_field >= value
        elif field_name.endswith("__to"):
            condition = model_field <= value
        elif field_name.endswith("__min"):
            condition = model_field >= value
        elif field_name.endswith("__max"):
            condition = model_field <= value
        else:
            condition = model_field == value

        if nulls_match:
            condition = or_(condition, model_field.is_(None))

        filters |= {condition}

    return filters
