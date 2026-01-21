import logging
import uuid
from typing import cast

from flask import Flask
from flask_jwt_extended import JWTManager

from .user_context import UserProtocol

logger = logging.getLogger(__name__)


def init_jwt(app: Flask) -> None:
    """Initialize JWTManager with user lookup callbacks.

    Args:
        app: Flask application to initialize JWT for

    Raises:
        RuntimeError: If JWT_SECRET_KEY is not set in production
            (when DEBUG and TESTING are both False)
    """
    # Import User here to avoid premature table creation
    from .models import User

    jwt_secret = app.config.get("JWT_SECRET_KEY")
    is_production = not app.debug and not app.testing

    if not jwt_secret:
        if is_production:
            raise RuntimeError(
                "JWT_SECRET_KEY is required in production. "
                "Set app.config['JWT_SECRET_KEY'] or the JWT_SECRET_KEY environment variable. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        logger.warning(
            "JWT_SECRET_KEY is not set. This is insecure and will raise an error in production. "
            "Set app.config['JWT_SECRET_KEY'] before deploying."
        )

    jwt = JWTManager()
    jwt.init_app(app)
    jwt._set_error_handler_callbacks(app)

    # Set up user_identity_lookup for JWT
    @jwt.user_identity_loader
    def user_identity_lookup(user: UserProtocol | uuid.UUID) -> str:
        return str(user)

    # Set up user_lookup_callback for JWT
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header: dict, jwt_data: dict) -> UserProtocol | None:
        from ..sqla import db
        from .user_context import _get_registered_user_class

        identity = jwt_data["sub"]
        user = db.session.get(User, uuid.UUID(identity))

        if user is None:
            return None

        # Check if user is an instance of the registered custom class
        registered_cls = _get_registered_user_class()
        if registered_cls is not None and isinstance(user, registered_cls):
            return cast(UserProtocol, user)

        return cast(UserProtocol, user)
