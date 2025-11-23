"""Error handling module for Flask-More-Smorest.

This module provides exception classes and error handlers for the application.
"""

from .exceptions import (
    ApiException,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    UnprocessableEntity,
    InternalServerError,
    DBError,
)
from .error_handlers import (
    server_error_handler,
    unauthorized_handler,
    handle_api_exception,
    handle_generic_exception,
    handle_db_exception,
)

__all__ = [
    # Exception classes
    "ApiException",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "UnprocessableEntity",
    "InternalServerError",
    "DBError",
    # Error handlers
    "server_error_handler",
    "unauthorized_handler",
    "handle_api_exception",
    "handle_generic_exception",
    "handle_db_exception",
]
