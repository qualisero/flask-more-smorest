from flask import request
from flask_smorest import Api as ApiOrig
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_jwt_extended import verify_jwt_in_request, exceptions as jwt_exceptions
from apispec.ext.marshmallow import resolver as default_resolver
from marshmallow import Schema

from .exceptions import UnauthorizedError, ForbiddenError


class Api(ApiOrig):
    """Api override"""

    def __init__(self, app=None, *, spec_kwargs=None):
        if spec_kwargs is None:
            spec_kwargs = {}
        ma_plugin = MarshmallowPlugin(schema_name_resolver=custom_schema_name_resolver)
        spec_kwargs["marshmallow_plugin"] = ma_plugin
        if app and not app.config.get("DISABLE_AUTH", False):
            spec_kwargs["security"] = [{"jwt": []}]
        super().__init__(app, spec_kwargs=spec_kwargs)

    def init_app(self, app, *pargs, **kwargs):
        app.config["API_SPEC_OPTIONS"] = {"components": {"securitySchemes": {}}}
        if "jwt" in app.config.get("AUTH_METHODS", []):
            app.config["API_SPEC_OPTIONS"]["components"]["securitySchemes"]["bearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "`Bearer $your_token_value` will be inserted as Authorization header.",
            }
            # TODO: implement OAuth2 flows
            # "adminOAuth": {
            #     "type": "oauth2",
            #     "flows": {
            #         "password": {
            #             "tokenUrl": "https://example.com/oauth/token",
            #             "scopes": {"admin": "Admin access", "user": "User access"},
            #         }
            #     },
            #     "description": "OAuth2 flow for role-based access (e.g. admin scope).",
            # },

        super().init_app(app, *pargs, **kwargs)

        @app.before_request
        def require_login():
            if not request.endpoint or request.endpoint.startswith("api-docs"):
                return
            admin_endpoint = False
            if request.endpoint in app.view_functions:
                fn = app.view_functions[request.endpoint]
                public_endpoint = getattr(fn, "_is_public", False)
                admin_endpoint = getattr(fn, "_is_admin", False)
                if hasattr(fn, "view_class"):
                    public_endpoint |= getattr(fn.view_class, "_is_public", False)
                    admin_endpoint |= getattr(fn.view_class, "_is_admin", False)
                    # Handle MethodView classes:
                    if actual_method := getattr(fn.view_class, request.method.lower(), None):
                        public_endpoint |= getattr(actual_method, "_is_public", False)
                        admin_endpoint |= getattr(actual_method, "_is_admin", False)
                if public_endpoint and not admin_endpoint:
                    return
            try:
                # NOTE: we do not completely skip auth if DISABLE_AUTH=1, in case the endpoint relies on current_user
                verify_jwt_in_request()
            except (jwt_exceptions.JWTDecodeError, jwt_exceptions.NoAuthorizationError) as e:
                if app.config.get("DISABLE_AUTH", False):
                    return
                raise UnauthorizedError(f"Invalid token ({e})")

            if admin_endpoint:
                from .user import User

                if not User.is_current_user_admin():
                    raise ForbiddenError("Admin access only")


def custom_schema_name_resolver(schema: type[Schema], **kwargs) -> str:
    # print(schema.__class__.__name__, getattr(schema, 'exclude', False))
    if getattr(schema, "partial", False):
        return ""
        # return default_resolver(schema) + 'Partial'
    if getattr(schema, "only", False):
        return ""
    if getattr(schema, "exclude", False):
        return ""

    if schema.__class__.__name__ == "NestedSchema":
        return ""

    return default_resolver(schema)
