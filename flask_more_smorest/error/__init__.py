"""Error handling module for Flask-More-Smorest.

This module provides exception classes and error handlers for the application.
"""

from .error_handlers import (
    handle_api_exception,
    handle_db_exception,
    handle_generic_exception,
    handle_integrity_error,
    server_error_handler,
    unauthorized_handler,
)
from .exceptions import (
    ApiException,
    BadRequestError,
    ConflictError,
    DBError,
    ForbiddenError,
    IntegrityConflict,
    InternalServerError,
    NotFoundError,
    ResourceInUse,
    UnauthorizedError,
    UnprocessableEntity,
)
from .integrity import Violation, parse_integrity_error, to_api_exception

__all__ = [
    "ApiException",
    "BadRequestError",
    "ConflictError",
    "DBError",
    "ForbiddenError",
    "IntegrityConflict",
    "InternalServerError",
    "NotFoundError",
    "ResourceInUse",
    "UnauthorizedError",
    "UnprocessableEntity",
    "Violation",
    "handle_api_exception",
    "handle_db_exception",
    "handle_generic_exception",
    "handle_integrity_error",
    "parse_integrity_error",
    "server_error_handler",
    "to_api_exception",
    "unauthorized_handler",
]
