"""Query filtering utilities for Flask-Smorest CRUD operations.

This module provides utilities for generating filter schemas and converting
filter parameters into SQLAlchemy query statements. It supports:
- Range queries for date/datetime fields (field__from, field__to)
- Min/max queries for numeric fields (field__min, field__max)
- Enum list filters (field__in)
"""

import copy
from typing import Mapping

import marshmallow as ma
from marshmallow import validate
from sqlalchemy import ColumnElement

from flask_more_smorest.sqla.base_model import BaseModel

_NUMERIC_FIELDS = (ma.fields.Integer, ma.fields.Float, ma.fields.Decimal)
_TEMPORAL_FIELDS = (ma.fields.DateTime, ma.fields.Date)


def _clone_field(field: ma.fields.Field) -> ma.fields.Field:
    new_field = copy.deepcopy(field)
    new_field.load_default = None
    new_field.load_only = True
    new_field.dump_only = False
    new_field.required = False
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
    excluded_fields: set[str] = set()

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
        else:
            excluded_fields.add(field_name)

        for new_name, new_field in new_fields.items():
            field_definitions[new_name] = new_field

    def _remove_none_fields(self: ma.Schema, data: dict, **kwargs: dict) -> dict:
        return {k: v for k, v in data.items() if v is not None}

    def _on_bind_field(self: ma.Schema, field_name: str, field_obj: ma.fields.Field) -> None:
        field_obj.load_default = None
        field_obj.load_only = True
        field_obj.dump_only = False
        field_obj.required = False

    base_meta = getattr(base_cls, "Meta", object)
    base_exclude: tuple[str, ...] = tuple(getattr(base_meta, "exclude", ()))
    combined_exclude = tuple(dict.fromkeys(base_exclude + tuple(sorted(excluded_fields))))

    meta_attrs: dict[str, object] = {
        "partial": True,
        "load_instance": False,
        "unknown": ma.RAISE,
    }
    if combined_exclude:
        meta_attrs["exclude"] = combined_exclude

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
        validate=validate.Range(min=1),
    )

    class_name = f"{base_cls.__name__}FilterSchema"
    FilterSchema: type[ma.Schema] = type(class_name, (base_cls,), attrs)
    return FilterSchema


def get_statements_from_filters(kwargs: Mapping, model: type[BaseModel]) -> set[ColumnElement[bool]]:
    """Convert query kwargs into SQLAlchemy filters based on the schema.

    This function processes filtering parameters and converts them to
    SQLAlchemy WHERE clause conditions, supporting:
    - Range queries: field__from (>=) and field__to (<=)
    - Numeric ranges: field__min (>=) and field__max (<=)
    - Exact equality: field = value

    Args:
        kwargs: Dictionary of filter parameters from the query string
        model: SQLAlchemy model class to filter on

    Returns:
        Set of SQLAlchemy filter conditions (BinaryExpression objects)

    Example:
        >>> filters = {'age__min': 18, 'age__max': 65, 'is_active': True}
        >>> stmts = get_statements_from_filters(filters, User)
        >>> results = User.query.filter(*stmts).all()
    """
    filters: set[ColumnElement[bool]] = set()

    for field_name, value in kwargs.items():
        if value is None:
            continue
        if field_name in ("page", "page_size"):
            # Skip pagination parameters as they are handled separately
            continue
        if field_name.endswith("__from"):
            base_field = getattr(model, field_name[:-6])
            filters |= {base_field >= value}
        elif field_name.endswith("__to"):
            base_field = getattr(model, field_name[:-4])
            filters |= {base_field <= value}
        elif field_name.endswith("__min"):
            base_field = getattr(model, field_name[:-5])
            filters |= {base_field >= value}
        elif field_name.endswith("__max"):
            base_field = getattr(model, field_name[:-5])
            filters |= {base_field <= value}
        else:
            filters |= {getattr(model, field_name) == value}

    return filters
