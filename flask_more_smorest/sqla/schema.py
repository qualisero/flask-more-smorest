"""Schema generation for SQLAlchemy models.

This module provides BaseSchema for Marshmallow schemas with automatic
view_args injection and schema generation utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import request
from marshmallow import fields, pre_load
from marshmallow_sqlalchemy import ModelConverter, SQLAlchemyAutoSchema

if TYPE_CHECKING:
    from sqlalchemy.orm.properties import ColumnProperty

    # Type alias for SQLAlchemy column or relationship property
    PropertyOrColumn = ColumnProperty[Any] | Any


class BaseSchema(SQLAlchemyAutoSchema):
    """Base schema for all Marshmallow schemas.

    This schema extends SQLAlchemyAutoSchema with automatic view_args
    injection for URL parameters and adds an is_writable field for
    permission checking.

    Attributes:
        is_writable: Read-only boolean field indicating if current user
                     can write to the resource

    Example:
        >>> class ArticleSchema(BaseSchema):
        ...     class Meta:
        ...         model = Article
        ...         include_relationships = True
    """

    is_writable = fields.Boolean(dump_only=True)

    @pre_load
    def pre_load(self, data: dict[str, str | int | float | bool], **kwargs: Any) -> dict[str, str | int | float | bool]:
        """Pre-load hook to handle UUID conversion and view_args injection.

        Automatically injects URL parameters from Flask's request.view_args
        into the data being loaded, allowing schemas to access route parameters.

        Args:
            data: The input data dictionary
            **kwargs: Additional keyword arguments from Marshmallow

        Returns:
            The modified data dictionary with view_args injected

        Example:
            Given a route `/articles/<uuid:article_id>` and a schema field
            `article_id`, the article_id from the URL will be automatically
            injected into the data if not already present.
        """

        if request and (args := request.view_args):
            for view_arg, val in args.items():
                if view_arg not in self.fields or self.fields[view_arg].dump_only or data.get(view_arg) is not None:
                    continue
                # TODO: Consider restricting automatic injection to fields marked as required.
                #       This would ensure that only mandatory identifiers (for example, IDs coming
                #       from the URL path) are populated from view_args, while optional fields
                #       remain controlled by the client payload. Changing this behavior could
                #       affect how partial updates are interpreted and may reduce surprising
                #       cases where non-required fields are implicitly filled from the route.
                data[view_arg] = val

        return data


class BaseModelConverter(ModelConverter):
    """Model converter for SQLAlchemy models with enhanced relationship handling.

    This converter extends marshmallow_sqlalchemy's ModelConverter to provide
    better handling of relationships, particularly around nullable constraints
    and dump_only settings.
    """

    def _add_relationship_kwargs(self, kwargs: dict[str, Any], prop: PropertyOrColumn) -> None:
        """Add keyword arguments to kwargs (in-place) based on the relationship property.

        This method determines the required/allow_none behavior based on the
        relationship's foreign key constraints and direction.

        Copied and adapted from marshmallow_sqlalchemy.convert.ModelConverter.

        Args:
            kwargs: Dictionary to update with relationship field configuration
            prop: SQLAlchemy relationship property to analyze
        """
        required = False
        allow_none = True
        for pair in prop.local_remote_pairs:
            if not pair[0].nullable and (prop.uselist is True or self.DIRECTION_MAPPING[prop.direction.name] is False):
                allow_none = False
                # Do not make required if a default is provided:
                if not pair[0].default and not pair[0].server_default:
                    required = True
        # NOTE: always set dump_only to True for relationships (can be overriden in schema)
        kwargs.update({"allow_none": allow_none, "required": required, "dump_only": True})


def create_model_schema(model_cls: type, *, db_session: Any = None) -> type[BaseSchema]:
    """Create a Marshmallow schema for a SQLAlchemy model class.

    This function generates a schema class with sensible defaults for
    CRUD operations, including relationship handling and automatic
    timestamp field management.

    Args:
        model_cls: SQLAlchemy model class to generate schema for
        db_session: SQLAlchemy session to use (if None, uses model_cls's session)

    Returns:
        Generated BaseSchema subclass for the model

    Example:
        >>> from flask_more_smorest.sqla import BaseModel
        >>> class Article(BaseModel):
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        >>>
        >>> ArticleSchema = create_model_schema(Article)
        >>> schema = ArticleSchema()
    """
    from .database import db

    if db_session is None:
        db_session = db.session

    return type(
        f"{model_cls.__name__}AutoSchema",
        (BaseSchema,),
        {
            "Meta": type(
                "Meta",
                (object,),
                {
                    "model": model_cls,
                    "include_relationships": True,
                    "include_fk": True,
                    "load_instance": True,
                    "sqla_session": db_session,
                    "model_converter": BaseModelConverter,
                    "dump_only": ("id", "created_at", "updated_at"),
                },
            )
        },
    )
