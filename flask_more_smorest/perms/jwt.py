import logging
import uuid

from flask import Flask
from flask_jwt_extended import JWTManager

from .user_models import User

logger = logging.getLogger(__name__)


def init_jwt(app: Flask) -> None:
    """Initialize JWTManager with user lookup callbacks."""

    if not app.config.get("JWT_SECRET_KEY"):
        logger.warning("JWT_SECRET_KEY is not set! This is insecure for production environments.")

    jwt = JWTManager()
    jwt.init_app(app)
    jwt._set_error_handler_callbacks(app)

    # Set up user_identity_lookup for JWT
    @jwt.user_identity_loader
    def user_identity_lookup(user: User | uuid.UUID) -> str:
        if isinstance(user, User):
            return str(user.id)
        return str(user)

    # Set up user_lookup_callback for JWT
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header: dict, jwt_data: dict) -> User | None:
        from ..sqla import db

        identity = jwt_data["sub"]
        return db.session.get(User, uuid.UUID(identity))
