"""CRUD Blueprint for automatic RESTful API generation with Flask-Smorest."""

from http import HTTPStatus
from importlib import import_module
from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING

from flask.views import MethodView
from marshmallow_sqlalchemy.load_instance_mixin import LoadInstanceMixin
from marshmallow import RAISE, Schema
from sqlalchemy.orm import DeclarativeBase

from .query_filtering import generate_filter_schema, get_statements_from_filters
from .utils import convert_snake_to_camel
from .enhanced_blueprint import EnhancedBlueprint

if TYPE_CHECKING:
    from flask import Flask


class CRUDBlueprint(EnhancedBlueprint):
    """Blueprint subclass that automatically registers CRUD routes.

    This class extends EnhancedBlueprint to provide automatic CRUD
    (Create, Read, Update, Delete) operations for SQLAlchemy models.
    It automatically generates RESTful endpoints based on the provided
    model and schema configuration.
    """

    def __init__(self, *pargs: Any, **kwargs: Any) -> None:
        """Initialize CRUD blueprint with model and schema configuration.

        Args:
            *pargs: Positional arguments (name, import_name)
            **kwargs: Keyword arguments including model, schema, and CRUD configuration
        """

        if len(pargs) > 0:
            name: str = pargs[0]
        else:
            name = kwargs.pop("name")

        if len(pargs) > 1:
            import_name: str = pargs[1]
        else:
            import_name = kwargs.pop("import_name", __name__)

        pargs = [name, import_name] + list(pargs[2:])

        if "url_prefix" not in kwargs:
            kwargs["url_prefix"] = f"/{name}/"

        # TODO: throw error if url_prefix does not end with "/"
        # # Enforce slash termination:
        # if not kwargs["url_prefix"].endswith("/"):
        #     kwargs["url_prefix"] += "/"

        model_name: str = kwargs.pop("model", convert_snake_to_camel(name.capitalize()))
        schema_name: str = kwargs.pop("schema", model_name + "Schema")
        res_id_name: str = kwargs.pop("res_id", "id")
        res_id_param_name: str = kwargs.pop("res_id_param", f"{name.lower()}_id")
        skip_methods: List[str] = kwargs.pop("skip_methods", [])
        methods_raw: Union[List[str], Dict[str, Dict[str, Any]]] = kwargs.pop(
            "methods", ["INDEX", "GET", "POST", "PATCH", "DELETE"]
        )
        if isinstance(methods_raw, list):
            methods: Dict[str, Dict[str, Any]] = {m: {} for m in methods_raw}
        else:
            methods = methods_raw
        for m in skip_methods:
            del methods[m]
        model_import_name = kwargs.pop("model_import_name", ".".join(import_name.split(".")[:-1] + ["models"]))
        schema_import_name = kwargs.pop("schema_import_name", ".".join(import_name.split(".")[:-1] + ["schemas"]))

        super().__init__(*pargs, **kwargs)

        ModelCls = getattr(import_module(model_import_name), model_name)
        ModelCls.__name__ = model_name

        SchemaCls = ModelCls.Schema
        try:
            schemaModule = import_module(schema_import_name)
            if hasattr(schemaModule, schema_name):
                SchemaCls = getattr(schemaModule, schema_name)
        except ImportError:
            pass

        if update_schema_name := methods.get("PATCH", {}).get("arg_schema"):
            if isinstance(update_schema_name, str):
                UpdateSchemaClsOrInst = getattr(import_module(name), update_schema_name)
            else:
                UpdateSchemaClsOrInst = update_schema_name
        else:
            if issubclass(SchemaCls, LoadInstanceMixin.Schema):
                UpdateSchemaClsOrInst = SchemaCls(partial=True, load_instance=False)
            else:
                UpdateSchemaClsOrInst = SchemaCls(partial=True)
            # NOTE: load_instance=False is not supported in fields.nested. Need to find another way to handle nested fields:
            # for _, field in UpdateSchemaClsOrInst.declared_fields.items():
            #     if isinstance(field, ma.fields.Nested) and not field.dump_only and callable(field.nested):
            #         field.nested = field.nested(load_instance=False)

        id_type = str(getattr(ModelCls, res_id_name).type).lower()
        if id_type.startswith("char"):
            # NOTE: Might need to differentiate between uuid and regular string IDs
            id_type = "uuid"

        if "INDEX" in methods or "POST" in methods:

            if "INDEX" in methods:
                IndexSchemaClass = methods["INDEX"].get("schema", SchemaCls)

                QueryFilterSchema = generate_filter_schema(base_schema=IndexSchemaClass)

            class GenericIndex(MethodView):
                """Index/Post endpoints."""

                if "INDEX" in methods:

                    @self.arguments(QueryFilterSchema, location="query", unknown=RAISE)
                    @self.response(HTTPStatus.OK, methods["INDEX"].get("schema", SchemaCls)(many=True))
                    @self.doc(operationId=f"list{model_name}")
                    def get(_self, filters):
                        """Fetch all resources."""

                        stmts = get_statements_from_filters(filters, model=ModelCls)
                        return ModelCls.query.filter(*stmts).all()

                if "POST" in methods:

                    @self.arguments(methods["POST"].get("schema", SchemaCls))
                    @self.response(HTTPStatus.OK, methods["POST"].get("schema", SchemaCls))
                    @self.doc(
                        responses={
                            HTTPStatus.NOT_FOUND: {"description": f"{name} resource not found"},
                            HTTPStatus.CONFLICT: {"description": "DB error."},
                        },
                        operationId=f"create{model_name}",
                    )
                    def post(_self, new_object, **kwargs):
                        """Create and return new resource."""
                        # NOTE: app should handle IntegrityError globally via errorhandler
                        new_object.update(kwargs)
                        new_object.save()
                        return new_object

            if hasattr(GenericIndex, "get"):
                GenericIndex.get.__doc__ = f"Fetch all {name} resources."
                if methods["INDEX"].get("is_admin", False):
                    self.admin_endpoint(GenericIndex.get)
            if hasattr(GenericIndex, "post"):
                GenericIndex.post.__doc__ = f"Create and return new {name}."
                if methods["POST"].get("is_admin", False):
                    self.admin_endpoint(GenericIndex.post)
            # Manually register after updating docstring:
            self.route("")(GenericIndex)

        class GenericCRUD(MethodView):
            """Resource-specific endpoints."""

            if "GET" in methods:

                @self.doc(
                    responses={HTTPStatus.NOT_FOUND: {"description": f"{name} not found"}},
                    operationId=f"get{model_name}",
                )
                @self.response(HTTPStatus.OK, methods["GET"].get("schema", SchemaCls))
                def get(_self, **kwargs):
                    """Fetch resource by ID."""
                    kwargs[res_id_name] = kwargs.pop(res_id_param_name)
                    return ModelCls.get_by_or_404(**kwargs)

            if "PATCH" in methods:

                @self.arguments(UpdateSchemaClsOrInst)
                @self.doc(
                    responses={
                        HTTPStatus.NOT_FOUND: {"description": f"{name} not found"},
                        HTTPStatus.CONFLICT: {"description": "DB error."},
                    },
                    operationId=f"update{model_name}",
                )
                @self.response(HTTPStatus.OK, methods["PATCH"].get("schema", SchemaCls))
                def patch(_self, payload, **kwargs):
                    """Update resource."""
                    kwargs[res_id_name] = kwargs.pop(res_id_param_name)
                    res = ModelCls.get_by_or_404(**kwargs)
                    # NOTE: app should handle IntegrityError globally via errorhandler
                    res.update(**payload)
                    return res

            if "DELETE" in methods:

                @self.response(HTTPStatus.NO_CONTENT, description=f"{name} deleted")
                @self.doc(
                    operationId=f"delete{model_name}",
                )
                def delete(_self, **kwargs):
                    """Delete resource."""
                    kwargs[res_id_name] = kwargs.pop(res_id_param_name)
                    res = ModelCls.get_by_or_404(**kwargs)
                    res.delete()
                    return "", HTTPStatus.NO_CONTENT

            if "PUT" in methods:
                raise NotImplementedError("PUT method is not implemented. Use PATCH instead.")

        if hasattr(GenericCRUD, "get"):
            GenericCRUD.get.__doc__ = f"Fetch {name} by ID."
            if methods["GET"].get("is_admin", False):
                self.admin_endpoint(GenericCRUD.get)
        if hasattr(GenericCRUD, "patch"):
            GenericCRUD.patch.__doc__ = f"Update {name} by ID."
            if methods["PATCH"].get("is_admin", False):
                self.admin_endpoint(GenericCRUD.patch)
        if hasattr(GenericCRUD, "delete"):
            GenericCRUD.delete.__doc__ = f"Delete {name} by ID."
            if methods["DELETE"].get("is_admin", False):
                self.admin_endpoint(GenericCRUD.delete)
        # if hasattr(GenericCRUD, "put"):
        #     GenericCRUD.put.__doc__ = f"Replace {name} resource."

        self.route(f"<{id_type}:{res_id_param_name}>")(GenericCRUD)
