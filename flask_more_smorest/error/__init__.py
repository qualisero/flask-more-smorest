"""Error handling module for Flask-More-Smorest.

This module provides exception classes and error handlers for the application.
"""

from .error_handlers import (
    handle_api_exception,
    handle_db_exception,
    handle_generic_exception,
    server_error_handler,
    unauthorized_handler,
)
from .exceptions import (
    ApiException,
    BadRequestError,
    DBError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableEntity,
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
