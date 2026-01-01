"""CRUD Blueprint for automatic RESTful API generation with Flask-Smorest.

This module provides a Blueprint subclass that automatically generates
RESTful CRUD (Create, Read, Update, Delete) endpoints for SQLAlchemy models
with Marshmallow schemas.
"""

import enum
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from importlib import import_module
from typing import TYPE_CHECKING, Any, Mapping, Sequence, TypedDict

import sqlalchemy as sa
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_sqlalchemy.session import Session
from marshmallow import RAISE, Schema
from marshmallow_sqlalchemy import SQLAlchemySchema
from sqlalchemy.orm import scoped_session

from flask_more_smorest.pagination import CRUDPaginationMixin
from flask_more_smorest.sqla.base_model import BaseModel

from ..utils import convert_snake_to_camel
from .query_filtering import generate_filter_schema, get_statements_from_filters

if TYPE_CHECKING:
    from flask_smorest.pagination import PaginationParameters


class CRUDMethod(enum.StrEnum):
    """Standard CRUD operations supported by CRUDBlueprint."""

    INDEX = "INDEX"
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"


class MethodConfig(TypedDict, total=False):
    """Configuration for a specific CRUD method."""

    schema: type[Schema] | str
    arg_schema: type[Schema] | str
    admin_only: bool


MethodConfigMapping = Mapping[CRUDMethod, MethodConfig | bool]


@dataclass
class CRUDConfig:
    """Configuration object for CRUD blueprint setup."""

    name: str
    url_prefix: str
    import_name: str
    model_cls: type[BaseModel]
    model_name: str
    schema_cls: type[Schema]
    schema_name: str
    schema_import_path: str
    model_import_path: str
    res_id_name: str
    res_id_param_name: str
    methods: dict[CRUDMethod, MethodConfig]

    if TYPE_CHECKING:
        from flask_smorest.pagination import PaginationParameters


class CRUDBlueprint(CRUDPaginationMixin, Blueprint):
    """Blueprint subclass that automatically registers CRUD routes.

    This class extends Flask-Smorest Blueprint to provide automatic CRUD
    (Create, Read, Update, Delete) operations for SQLAlchemy models.
    It automatically generates RESTful endpoints based on the provided
    model and schema configuration.

    Args:
        name: Blueprint name (first positional arg)
        import_name: Import name (second positional arg)
        *pargs, **kwargs: Additional keyword arguments for CRUD configuration passed to CRUDConfig

    Example:
        >>> blueprint = CRUDBlueprint(
        ...     'users', __name__,
        ...     model='User',
        ...     schema='UserSchema'
        ... )
    """

    _db_session: Session | scoped_session[Session]

    def __init__(
        self,
        name: str,
        import_name: str,
        model: type[BaseModel] | str | None = None,
        schema: type[Schema] | str | None = None,
        model_import_name: str | None = None,
        schema_import_name: str | None = None,
        res_id: str = "id",
        res_id_param: str | None = None,
        methods: list[CRUDMethod] | MethodConfigMapping = list(CRUDMethod),
        skip_methods: list[CRUDMethod] = [],
        db_session: Session | scoped_session[Session] | None = None,
        static_folder: str | None = None,
        static_url_path: str | None = None,
        template_folder: str | None = None,
        url_prefix: str | None = None,
        subdomain: str | None = None,
        url_defaults: dict[str, Any] | None = None,
        root_path: str | None = None,
        cli_group: str | None = None,
    ) -> None:
        """Initialize CRUD blueprint with model and schema configuration."""
        if db_session is None:
            from flask_more_smorest.sqla import db

            self._db_session = db.session
        else:
            self._db_session = db_session

        config = self._build_config(
            name=name,
            import_name=import_name,
            model=model,
            schema=schema,
            model_import_name=model_import_name,
            schema_import_name=schema_import_name,
            res_id=res_id,
            res_id_param=res_id_param,
            methods=methods,
            skip_methods=skip_methods,
            url_prefix=url_prefix,
        )

        super().__init__(
            name,
            import_name,
            static_folder=static_folder,
            static_url_path=static_url_path,
            template_folder=template_folder,
            url_prefix=url_prefix or config.url_prefix,
            subdomain=subdomain,
            url_defaults=url_defaults,
            root_path=root_path,
            cli_group=cli_group,
        )

        update_schema = self._prepare_update_schema(config)
        self._register_crud_routes(config, update_schema)

    def _build_config(
        self,
        name: str,
        import_name: str,
        model: type[BaseModel] | str | None,
        schema: type[Schema] | str | None,
        model_import_name: str | None,
        schema_import_name: str | None,
        res_id: str,
        res_id_param: str | None,
        methods: list[CRUDMethod] | MethodConfigMapping,
        skip_methods: list[CRUDMethod],
        url_prefix: str | None,
    ) -> CRUDConfig:
        """Build and validate configuration."""

        resolved_url_prefix: str = url_prefix or f"/{name}/"

        resolved_model_import_path: str = model_import_name or ".".join(import_name.split(".")[:-1] + ["models"])
        resolved_schema_import_path: str = schema_import_name or ".".join(import_name.split(".")[:-1] + ["schemas"])

        model_or_name = model or convert_snake_to_camel(name.capitalize())
        model_cls: type[BaseModel]
        if isinstance(model_or_name, str):
            try:
                model_cls = getattr(import_module(resolved_model_import_path), model_or_name)
            except (ImportError, AttributeError) as e:
                raise ValueError(
                    f"Could not import model '{model_or_name}' from '{resolved_model_import_path}'."
                ) from e
            model_cls.__name__ = model_or_name
        elif isinstance(model_or_name, type) and issubclass(model_or_name, BaseModel):
            model_cls = model_or_name
        else:
            raise ValueError("CRUDBlueprint 'model' argument must be a string or a BaseModel subclass.")

        schema_or_name = schema
        schema_cls: type[Schema]

        if schema_or_name is None:
            schema_or_name = model_cls.Schema

        if isinstance(schema_or_name, str):
            try:
                schema_module = import_module(resolved_schema_import_path)
                if hasattr(schema_module, schema_or_name):
                    schema_cls = getattr(schema_module, schema_or_name)
            except (ImportError, AttributeError) as e:
                raise ValueError(
                    f"Could not import schema '{schema_or_name}' from '{resolved_schema_import_path}'."
                ) from e
        elif isinstance(schema_or_name, type) and issubclass(schema_or_name, Schema):
            schema_cls = schema_or_name
        else:
            raise ValueError("CRUDBlueprint 'schema' argument must be a string or a Schema subclass.")

        res_id_param_name: str = res_id_param or f"{name.lower()}_id"

        normalized_methods = self._normalize_methods(methods)

        for m in skip_methods:
            normalized_methods.pop(CRUDMethod(m), None)

        return CRUDConfig(
            name=name,
            url_prefix=resolved_url_prefix,
            import_name=import_name,
            model_cls=model_cls,
            model_name=model_cls.__name__,
            schema_cls=schema_cls,
            schema_name=schema_cls.__name__,
            schema_import_path=resolved_schema_import_path,
            model_import_path=resolved_model_import_path,
            res_id_name=res_id,
            res_id_param_name=res_id_param_name,
            methods=normalized_methods,
        )

    def _normalize_methods(
        self,
        methods_raw: list[CRUDMethod] | MethodConfigMapping,
    ) -> dict[CRUDMethod, MethodConfig]:
        """Normalize different method inputs into a standard dict."""

        normalized: dict[CRUDMethod, MethodConfig] = {}

        if isinstance(methods_raw, list):
            for item in methods_raw:
                key = CRUDMethod(item)
                normalized[key] = {}
            return normalized

        if not isinstance(methods_raw, Mapping):
            raise TypeError("CRUDBlueprint 'methods' argument must be a list or a dict.")

        for method, config in methods_raw.items():
            key = CRUDMethod(method)
            if config is True:
                normalized[key] = {}
            elif config is False:
                continue
            elif isinstance(config, dict):
                normalized[key] = config
            else:
                raise TypeError("CRUDBlueprint method config entries must be dicts, True for defaults, or omitted")

        return normalized

    def _prepare_update_schema(
        self, config: CRUDConfig
    ) -> Schema | type[Schema] | SQLAlchemySchema | type[SQLAlchemySchema]:
        """Create update schema for PATCH operations.

        Args:
            config: Configuration object

        Returns:
            Update schema instance or class
        """

        update_schema: Schema | type[Schema] | SQLAlchemySchema | type[SQLAlchemySchema]

        if update_schema_arg := config.methods.get(CRUDMethod.PATCH, {}).get("arg_schema"):
            # Explicit patch schema provided
            if isinstance(update_schema_arg, str):
                try:
                    schema_module = import_module(config.schema_import_path)
                    update_schema = getattr(schema_module, update_schema_arg)
                except (ImportError, AttributeError) as e:
                    raise ValueError(
                        f"Could not import schema '{update_schema_arg}' from '{config.schema_import_path}'."
                    ) from e
            elif isinstance(update_schema_arg, type) and issubclass(update_schema_arg, Schema):
                update_schema = update_schema_arg
            else:
                raise TypeError("PATCH 'arg_schema' must be a string or Schema class/instance.")
        else:
            # NOTE: the following will trigger a warning in apispec if no custom resolver is set
            update_schema = config.schema_cls(partial=True)
            if isinstance(update_schema, SQLAlchemySchema):
                update_schema._load_instance = False

        return update_schema

    def _register_crud_routes(
        self,
        config: CRUDConfig,
        update_schema: Schema | type[Schema],
    ) -> None:
        """Register all CRUD routes for the blueprint.

        Args:
            config: Configuration object
            update_schema: Update schema for PATCH operations
        """
        id_type = str(getattr(config.model_cls, config.res_id_name).type).lower()
        if id_type.startswith("char"):
            id_type = "uuid"
        model_cls: type[BaseModel] = config.model_cls
        schema_cls: type[Schema] = config.schema_cls

        if CRUDMethod.INDEX in config.methods or CRUDMethod.POST in config.methods:
            if CRUDMethod.INDEX in config.methods:
                cls = config.methods[CRUDMethod.INDEX].get("schema", schema_cls)
                if not isinstance(cls, type(Schema)):
                    raise TypeError(f"Expected Schema class for INDEX['schema'], got {type(cls)}")
                index_schema_class: type[Schema] = cls
                query_filter_schema = generate_filter_schema(base_schema=index_schema_class)

            class GenericIndex(MethodView):
                """Index/Post endpoints."""

                if CRUDMethod.INDEX in config.methods:

                    @self.arguments(query_filter_schema, location="query", unknown=RAISE)
                    @self.response(HTTPStatus.OK, index_schema_class(many=True))
                    @self.paginate()
                    @self.doc(operationId=f"list{config.model_name}")
                    def get(
                        _self,
                        filters: dict,
                        pagination_parameters: "PaginationParameters",
                        **kwargs: Any,
                    ) -> Sequence[BaseModel]:
                        """Fetch all resources.
                        kwargs might contains path parameters to filter by (eg /user/<uuid:user_id>/roles/)"""

                        stmts = get_statements_from_filters(filters, model=model_cls)
                        query = sa.select(model_cls).filter_by(**kwargs).filter(*stmts)

                        # Handle pagination
                        # Count total items
                        count_query = sa.select(sa.func.count()).select_from(query.subquery())
                        total_items = self._db_session.scalar(count_query)
                        pagination_parameters.item_count = total_items  # pyright: ignore[reportAttributeAccessIssue]

                        # Apply limit/offset
                        query = query.limit(pagination_parameters.page_size).offset(
                            pagination_parameters.page_size * (pagination_parameters.page - 1)
                        )

                        res = self._db_session.execute(query)
                        return res.scalars().all()

                if CRUDMethod.POST in config.methods:

                    @self.arguments(config.methods[CRUDMethod.POST].get("schema", schema_cls))
                    @self.response(HTTPStatus.OK, config.methods[CRUDMethod.POST].get("schema", schema_cls))
                    @self.doc(
                        responses={
                            HTTPStatus.NOT_FOUND: {"description": f"{config.name} resource not found"},
                            HTTPStatus.CONFLICT: {"description": "DB error."},
                        },
                        operationId=f"create{config.model_name}",
                    )
                    def post(
                        _self, new_object: BaseModel, **kwargs: str | int | float | bool | bytes | None
                    ) -> BaseModel:
                        """Create and return new resource."""
                        new_object.update(commit=True, **kwargs)
                        new_object.save()
                        return new_object

            self._configure_endpoint(
                GenericIndex, "get", f"Fetch all {config.name} resources.", config.methods.get(CRUDMethod.INDEX, {})
            )
            self._configure_endpoint(
                GenericIndex, "post", f"Create and return new {config.name}.", config.methods.get(CRUDMethod.POST, {})
            )
            self.route("")(GenericIndex)

        class GenericCRUD(MethodView):
            """Resource-specific endpoints."""

            if CRUDMethod.GET in config.methods:

                @self.doc(
                    responses={HTTPStatus.NOT_FOUND: {"description": f"{config.name} not found"}},
                    operationId=f"get{config.model_name}",
                )
                @self.response(HTTPStatus.OK, config.methods[CRUDMethod.GET].get("schema", schema_cls))
                def get(_self, **kwargs: Any) -> BaseModel:
                    """Fetch resource by ID."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    res = model_cls.get_by_or_404(**kwargs)
                    return res

            if CRUDMethod.PATCH in config.methods:

                @self.arguments(update_schema)
                @self.doc(
                    responses={
                        HTTPStatus.NOT_FOUND: {"description": f"{config.name} not found"},
                        HTTPStatus.CONFLICT: {"description": "DB error."},
                    },
                    operationId=f"update{config.model_name}",
                )
                @self.response(HTTPStatus.OK, config.methods[CRUDMethod.PATCH].get("schema", schema_cls))
                def patch(_self, payload: dict, **kwargs: str | int | uuid.UUID | bool | None) -> BaseModel:
                    """Update resource."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    res = model_cls.get_by_or_404(**kwargs)
                    res.update(**payload)
                    return res

            if CRUDMethod.DELETE in config.methods:

                @self.response(HTTPStatus.NO_CONTENT, description=f"{config.name} deleted")
                @self.doc(operationId=f"delete{config.model_name}")
                def delete(_self, **kwargs: str | int | uuid.UUID | bool | None) -> tuple[str, int]:
                    """Delete resource."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    res = model_cls.get_by_or_404(**kwargs)
                    res.delete()
                    return "", HTTPStatus.NO_CONTENT

            if "PUT" in config.methods:
                raise NotImplementedError("PUT method is not implemented. Use PATCH instead.")

        self._configure_endpoint(
            GenericCRUD, "get", f"Fetch {config.name} by ID.", config.methods.get(CRUDMethod.GET, {})
        )
        self._configure_endpoint(
            GenericCRUD, "patch", f"Update {config.name} by ID.", config.methods.get(CRUDMethod.PATCH, {})
        )
        self._configure_endpoint(
            GenericCRUD, "delete", f"Delete {config.name} by ID.", config.methods.get(CRUDMethod.DELETE, {})
        )

        self.route(f"<{id_type}:{config.res_id_param_name}>")(GenericCRUD)

    def _configure_endpoint(
        self,
        view_cls: type[MethodView],
        method_name: str,
        docstring: str,
        method_config: MethodConfig,
    ) -> None:
        """Configure endpoint with docstring and admin decorator if needed.

        Args:
            view_cls: MethodView class containing the endpoint
            method_name: Name of the method to configure
            docstring: Docstring to set on the method
            method_config: Configuration dict for the method
        """
        if hasattr(view_cls, method_name):
            method = getattr(view_cls, method_name)
            method.__doc__ = docstring
            if method_config.get("admin_only", False):
                from ..perms import PermsBlueprintMixin

                if isinstance(self, PermsBlueprintMixin):
                    self.admin_endpoint(method)
                else:
                    raise TypeError("Blueprint must inherit from PermsBlueprintMixin to set admin_only endpoint.")
