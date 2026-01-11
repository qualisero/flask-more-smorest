"""Extended Flask-Smorest API with authentication and permission support.

This module provides an Api class that extends Flask-Smorest's Api with
JWT authentication, permission checking, custom schema name resolution,
and health check endpoint.
"""

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.ext.marshmallow import resolver as default_resolver
from flask import jsonify, request
from flask_jwt_extended import exceptions as jwt_exceptions
from flask_jwt_extended import verify_jwt_in_request
from flask_smorest import Api as ApiOrig
from marshmallow import Schema

from ..error.exceptions import ForbiddenError, UnauthorizedError
from .jwt import init_jwt

if TYPE_CHECKING:
    from flask import Flask, Response

logger = logging.getLogger(__name__)


class Api(ApiOrig):
    """Extended Api with JWT authentication and permission checking.

    This class extends Flask-Smorest's Api to automatically:
    - Configure JWT authentication in OpenAPI spec
    - Enforce authentication on non-public endpoints
    - Check admin permissions on admin-only endpoints
    - Customize schema naming for OpenAPI

    Example:
        >>> from flask import Flask
        >>> from flask_more_smorest.perms import Api
        >>>
        >>> app = Flask(__name__)
        >>> api = Api(app)
    """

    def __init__(self, app: "Flask | None" = None, *, spec_kwargs: dict | None = None) -> None:
        """Initialize the API with custom Marshmallow plugin.

        Args:
            app: Optional Flask application
            spec_kwargs: Optional keyword arguments for APISpec
        """
        if spec_kwargs is None:
            spec_kwargs = {}
        ma_plugin = MarshmallowPlugin(schema_name_resolver=custom_schema_name_resolver)
        spec_kwargs["marshmallow_plugin"] = ma_plugin
        if app and not app.config.get("DISABLE_AUTH", False):
            spec_kwargs["security"] = [{"jwt": []}]

        super().__init__(app, spec_kwargs=spec_kwargs)

    def init_app(self, app: "Flask", *pargs: str, **kwargs: dict) -> None:
        """Initialize the API with a Flask application.

        Sets up OpenAPI security schemes and before_request handler
        for authentication and authorization.

        Args:
            app: Flask application to initialize
            *pargs: Additional positional arguments
            **kwargs: Additional keyword arguments
        """

        init_jwt(app)

        spec_options = dict(app.config.get("API_SPEC_OPTIONS", {}))
        components = dict(spec_options.get("components", {}))
        security_schemes = dict(components.get("securitySchemes", {}))

        if "jwt" in app.config.get("AUTH_METHODS", []):
            security_schemes["bearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "`Bearer $your_token_value` will be inserted as Authorization header.",
            }

        components["securitySchemes"] = security_schemes
        spec_options["components"] = components
        app.config["API_SPEC_OPTIONS"] = spec_options
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

        # Register health check endpoint
        self._register_health_endpoint(app)

        extensions_state = app.extensions.setdefault("flask-more-smorest", {})
        if not extensions_state.get("require_login_registered", False):

            @app.before_request
            def require_login() -> None:
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
                    # NOTE: we do not completely skip auth if DISABLE_AUTH=1, in case the endpoint relies on authenticated user context
                    verify_jwt_in_request()
                except (
                    jwt_exceptions.JWTDecodeError,
                    jwt_exceptions.NoAuthorizationError,
                ) as e:
                    if app.config.get("DISABLE_AUTH", False):
                        return
                    raise UnauthorizedError(f"Invalid token ({e})")

                if admin_endpoint:
                    from .user_context import is_current_user_admin

                    if not is_current_user_admin():
                        raise ForbiddenError("Admin access only")

            extensions_state["require_login_registered"] = True

    def _register_health_endpoint(self, app: "Flask") -> None:
        """Register /health endpoint for monitoring and load balancers.

        The health endpoint provides:
        - Application status (healthy/unhealthy)
        - Database connectivity check
        - Timestamp and version information

        This endpoint is public and does not require authentication.

        Args:
            app: Flask application to register the endpoint on
        """
        from .. import __version__

        # Allow customizing the health endpoint path
        health_path = app.config.get("HEALTH_ENDPOINT_PATH", "/health")

        # Skip if disabled
        if not app.config.get("HEALTH_ENDPOINT_ENABLED", True):
            logger.debug("Health endpoint disabled via HEALTH_ENDPOINT_ENABLED=False")
            return

        @app.route(health_path)
        def health_check() -> tuple["Response", int]:
            """Health check endpoint for load balancers and monitoring.

            Returns:
                JSON response with health status and 200/503 status code
            """
            from ..sqla import db

            health: dict[str, Any] = {
                "status": "healthy",
                "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                "version": __version__,
            }

            # Check database connectivity
            try:
                db.session.execute(sa.text("SELECT 1"))
                health["database"] = "connected"
            except Exception as e:
                logger.error("Health check failed: database error - %s", str(e))
                health["database"] = "error"
                health["status"] = "unhealthy"
                return jsonify(health), 503

            return jsonify(health), 200

        # Mark as public endpoint
        health_check._is_public = True  # type: ignore[attr-defined]

        logger.debug("Registered health endpoint at %s", health_path)


def custom_schema_name_resolver(schema: type[Schema], **kwargs: str | bool) -> str:
    """Custom schema name resolver for OpenAPI spec.

    Filters out partial, only, and exclude schemas to keep the
    OpenAPI spec clean and avoid duplicate schema definitions.

    Args:
        schema: Marshmallow schema class to resolve name for
        **kwargs: Additional keyword arguments

    Returns:
        Empty string for partial/filtered schemas, default name otherwise
    """
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
