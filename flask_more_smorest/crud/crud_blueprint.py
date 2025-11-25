"""CRUD Blueprint for automatic RESTful API generation with Flask-Smorest.

This module provides a Blueprint subclass that automatically generates
RESTful CRUD (Create, Read, Update, Delete) endpoints for SQLAlchemy models
with Marshmallow schemas.
"""

from http import HTTPStatus
from importlib import import_module
from typing import TYPE_CHECKING

from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import RAISE, Schema

# from marshmallow_sqlalchemy.load_instance_mixin import LoadInstanceMixin

from ..utils import convert_snake_to_camel
from .query_filtering import generate_filter_schema, get_statements_from_filters

if TYPE_CHECKING:
    from ..sqla.base_model import BaseModel


class CRUDConfig:
    """Configuration object for CRUD blueprint setup.

    Attributes:
        name: Blueprint name
        import_name: Import name for the blueprint
        model_name: Model class name
        schema_name: Schema class name
        res_id_name: Name of the ID field on the model
        res_id_param_name: Name of the URL parameter for the ID
        methods: Dictionary of HTTP methods to generate
        model_import_name: Module path to import model from
        schema_import_name: Module path to import schema from
    """

    def __init__(
        self,
        name: str,
        url_prefix: str,
        import_name: str,
        model_name: str,
        schema_name: str,
        res_id_name: str,
        res_id_param_name: str,
        methods: dict[str, dict[str, Schema | str | bool]],
        model_import_name: str,
        schema_import_name: str,
    ):
        self.name = name
        self.url_prefix = url_prefix
        self.import_name = import_name
        self.model_name = model_name
        self.schema_name = schema_name
        self.res_id_name = res_id_name
        self.res_id_param_name = res_id_param_name
        self.methods = methods
        self.model_import_name = model_import_name
        self.schema_import_name = schema_import_name


class CRUDBlueprint(Blueprint):
    """Blueprint subclass that automatically registers CRUD routes.

    This class extends Flask-Smorest Blueprint to provide automatic CRUD
    (Create, Read, Update, Delete) operations for SQLAlchemy models.
    It automatically generates RESTful endpoints based on the provided
    model and schema configuration.

    Args:
        name: Blueprint name (first positional arg)
        import_name: Import name (second positional arg)
        model: Model class name (default: derived from name)
        schema: Schema class name (default: ModelName + "Schema")
        res_id: Name of the ID field on the model (default: "id")
        res_id_param: Name of the URL parameter for the ID (default: "{name}_id")
        skip_methods: List of methods to skip (default: [])
        methods: List or dict of HTTP methods to generate (default: all CRUD methods)
        model_import_name: Module path to import model from
        schema_import_name: Module path to import schema from
        **kwargs: Additional Blueprint arguments

    Example:
        >>> blueprint = CRUDBlueprint(
        ...     'users', __name__,
        ...     model='User',
        ...     schema='UserSchema'
        ... )
    """

    def __init__(self, *pargs: str, **kwargs: list[str] | dict[str, dict[str, Schema | str | bool]]) -> None:
        """Initialize CRUD blueprint with model and schema configuration.

        Args:
            *pargs: Positional arguments (name, import_name, etc.)
            **kwargs: Keyword arguments including model, schema, and CRUD configuration
        """
        config = self._parse_config(pargs, kwargs)

        super().__init__(config.name, config.import_name, *pargs[2:], **kwargs)

        model_cls, schema_cls = self._load_classes(config)
        update_schema = self._prepare_update_schema(schema_cls, config)
        self._register_crud_routes(config, model_cls, schema_cls, update_schema)

    def _parse_config(
        self, pargs: tuple[str, ...], kwargs: dict[str, list[str] | dict[str, dict[str, Schema | str | bool]]]
    ) -> CRUDConfig:
        """Parse and validate configuration from args and kwargs.

        Args:
            pargs: Positional arguments
            kwargs: Keyword arguments

        Returns:
            CRUDConfig object with validated configuration
        """
        if len(pargs) > 0:
            name: str = pargs[0]
        else:
            if "name" not in kwargs:
                raise ValueError("CRUDBlueprint requires a 'name' argument.")
            name = str(kwargs.pop("name"))

        if len(pargs) > 1:
            import_name: str = pargs[1]
        else:
            import_name = str(kwargs.pop("import_name", __name__))

        url_prefix: str = str(kwargs.get("url_prefix", f"/{name}/"))

        model_name: str = str(kwargs.pop("model", convert_snake_to_camel(name.capitalize())))
        schema_name: str = str(kwargs.pop("schema", model_name + "Schema"))
        res_id_name: str = str(kwargs.pop("res_id", "id"))
        res_id_param_name: str = str(kwargs.pop("res_id_param", f"{name.lower()}_id"))
        skip_methods: list[str] = list(kwargs.pop("skip_methods", []))
        methods_raw: list[str] | dict[str, dict[str, Schema | str | bool]] = kwargs.pop(
            "methods", ["INDEX", "GET", "POST", "PATCH", "DELETE"]
        )

        if isinstance(methods_raw, list):
            methods: dict[str, dict[str, Schema | str | bool]] = {m: {} for m in methods_raw}
        else:
            methods = methods_raw

        for m in skip_methods:
            del methods[m]

        model_import_name: str = str(
            kwargs.pop("model_import_name", ".".join(import_name.split(".")[:-1] + ["models"]))
        )
        schema_import_name: str = str(
            kwargs.pop("schema_import_name", ".".join(import_name.split(".")[:-1] + ["schemas"]))
        )

        return CRUDConfig(
            name=name,
            url_prefix=url_prefix,
            import_name=import_name,
            model_name=model_name,
            schema_name=schema_name,
            res_id_name=res_id_name,
            res_id_param_name=res_id_param_name,
            methods=methods,
            model_import_name=model_import_name,
            schema_import_name=schema_import_name,
        )

    def _load_classes(self, config: CRUDConfig) -> tuple[type["BaseModel"], type[Schema]]:
        """Load model and schema classes from module imports.

        Args:
            config: Configuration object

        Returns:
            Tuple of (model_class, schema_class)
        """
        model_cls = getattr(import_module(config.model_import_name), config.model_name)
        model_cls.__name__ = config.model_name

        schema_cls = model_cls.Schema
        try:
            schema_module = import_module(config.schema_import_name)
            if hasattr(schema_module, config.schema_name):
                schema_cls = getattr(schema_module, config.schema_name)
        except ImportError:
            # TODO: Log warning about missing schema module (and provide explicit way to rely on auto loading)
            pass

        return model_cls, schema_cls

    def _prepare_update_schema(self, schema_cls: type[Schema], config: CRUDConfig) -> Schema | type[Schema]:
        """Create update schema for PATCH operations.

        Args:
            schema_cls: Base schema class
            config: Configuration object

        Returns:
            Update schema instance or class
        """
        schema_module = import_module(config.schema_import_name)

        if update_schema_name := config.methods.get("PATCH", {}).get("arg_schema"):
            # Explicit patch schema provided
            if isinstance(update_schema_name, str):
                return getattr(schema_module, update_schema_name)
            elif (isinstance(update_schema_name, type) and issubclass(update_schema_name, Schema)) or isinstance(
                update_schema_name, Schema
            ):
                return update_schema_name
            else:
                raise TypeError("PATCH 'arg_schema' must be a string or Schema class/instance.")

        update_schema = schema_cls(partial=True)
        if hasattr(update_schema, "_load_instance"):
            update_schema._load_instance = False  # type: ignore[attr-defined]
        return update_schema

    def _register_crud_routes(
        self,
        config: CRUDConfig,
        model_cls: type["BaseModel"],
        schema_cls: type[Schema],
        update_schema: Schema | type[Schema],
    ) -> None:
        """Register all CRUD routes for the blueprint.

        Args:
            config: Configuration object
            model_cls: Model class
            schema_cls: Schema class
            update_schema: Update schema for PATCH operations
        """
        id_type = str(getattr(model_cls, config.res_id_name).type).lower()
        if id_type.startswith("char"):
            id_type = "uuid"

        if "INDEX" in config.methods or "POST" in config.methods:
            if "INDEX" in config.methods:
                index_schema_class = config.methods["INDEX"].get("schema", schema_cls)
                if not isinstance(index_schema_class, type(Schema)):
                    raise TypeError(f"Expected Schema class for INDEX['schema'], got {type(index_schema_class)}")
                query_filter_schema = generate_filter_schema(base_schema=index_schema_class)

            class GenericIndex(MethodView):
                """Index/Post endpoints."""

                if "INDEX" in config.methods:

                    @self.arguments(query_filter_schema, location="query", unknown=RAISE)
                    @self.response(HTTPStatus.OK, index_schema_class(many=True))
                    @self.doc(operationId=f"list{config.model_name}")
                    def get(_self, filters):
                        """Fetch all resources."""
                        stmts = get_statements_from_filters(filters, model=model_cls)
                        return model_cls.query.filter(*stmts).all()

                if "POST" in config.methods:

                    @self.arguments(config.methods["POST"].get("schema", schema_cls))
                    @self.response(HTTPStatus.OK, config.methods["POST"].get("schema", schema_cls))
                    @self.doc(
                        responses={
                            HTTPStatus.NOT_FOUND: {"description": f"{config.name} resource not found"},
                            HTTPStatus.CONFLICT: {"description": "DB error."},
                        },
                        operationId=f"create{config.model_name}",
                    )
                    def post(_self, new_object, **kwargs):
                        """Create and return new resource."""
                        new_object.update(kwargs)
                        new_object.save()
                        return new_object

            self._configure_endpoint(
                GenericIndex, "get", f"Fetch all {config.name} resources.", config.methods.get("INDEX", {})
            )
            self._configure_endpoint(
                GenericIndex, "post", f"Create and return new {config.name}.", config.methods.get("POST", {})
            )
            self.route("")(GenericIndex)

        class GenericCRUD(MethodView):
            """Resource-specific endpoints."""

            if "GET" in config.methods:

                @self.doc(
                    responses={HTTPStatus.NOT_FOUND: {"description": f"{config.name} not found"}},
                    operationId=f"get{config.model_name}",
                )
                @self.response(HTTPStatus.OK, config.methods["GET"].get("schema", schema_cls))
                def get(_self, **kwargs):
                    """Fetch resource by ID."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    return model_cls.get_by_or_404(**kwargs)

            if "PATCH" in config.methods:

                @self.arguments(update_schema)
                @self.doc(
                    responses={
                        HTTPStatus.NOT_FOUND: {"description": f"{config.name} not found"},
                        HTTPStatus.CONFLICT: {"description": "DB error."},
                    },
                    operationId=f"update{config.model_name}",
                )
                @self.response(HTTPStatus.OK, config.methods["PATCH"].get("schema", schema_cls))
                def patch(_self, payload, **kwargs):
                    """Update resource."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    res = model_cls.get_by_or_404(**kwargs)
                    res.update(**payload)
                    return res

            if "DELETE" in config.methods:

                @self.response(HTTPStatus.NO_CONTENT, description=f"{config.name} deleted")
                @self.doc(operationId=f"delete{config.model_name}")
                def delete(_self, **kwargs):
                    """Delete resource."""
                    kwargs[config.res_id_name] = kwargs.pop(config.res_id_param_name)
                    res = model_cls.get_by_or_404(**kwargs)
                    res.delete()
                    return "", HTTPStatus.NO_CONTENT

            if "PUT" in config.methods:
                raise NotImplementedError("PUT method is not implemented. Use PATCH instead.")

        self._configure_endpoint(GenericCRUD, "get", f"Fetch {config.name} by ID.", config.methods.get("GET", {}))
        self._configure_endpoint(GenericCRUD, "patch", f"Update {config.name} by ID.", config.methods.get("PATCH", {}))
        self._configure_endpoint(
            GenericCRUD, "delete", f"Delete {config.name} by ID.", config.methods.get("DELETE", {})
        )

        self.route(f"<{id_type}:{config.res_id_param_name}>")(GenericCRUD)

    def _configure_endpoint(
        self,
        view_cls: type[MethodView],
        method_name: str,
        docstring: str,
        method_config: dict[str, Schema | str | bool],
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


def check_schema_or_schema_instance(obj: object) -> None:
    """Test if the object is a Schema class or instance and raises TypeError if not.

    Args:
        obj: Object to test

    Returns:
    """
    if not ((isinstance(obj, type) and issubclass(obj, Schema)) or isinstance(obj, Schema)):
        raise TypeError(f"Expected Schema class or instance, got {type(obj)}")
