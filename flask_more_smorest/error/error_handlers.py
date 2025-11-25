"""Error handlers for Flask-More-Smorest.

This module provides error handler functions and a RequestHandlers class
for registering error handlers with Flask applications.
"""

import logging
from typing import TYPE_CHECKING

from flask import make_response
from sqlalchemy.exc import DatabaseError
from werkzeug.exceptions import HTTPException

from .exceptions import ApiException, DBError, ForbiddenError
from .exceptions import InternalServerError as ApiInternalServerError

if TYPE_CHECKING:
    from flask import Flask, Response

logger = logging.getLogger(__name__)


def server_error_handler(e: Exception) -> "Response":
    """Handle unhandled server errors.

    Args:
        e: The exception that was raised

    Returns:
        Flask Response with error details
    """
    exc = ApiInternalServerError(message=f"Unhandled Exception: {e}")

    logger.critical(
        "Encountered Unhandled Exception!",
        extra=exc.get_debug_context(),
    )

    return exc.make_error_response()


def unauthorized_handler(
    e: Exception, errors: dict[str, str] | None = None, level: str = "info", warnings: list[str] | None = None
) -> "Response":
    """Handle unauthorized access errors.

    Args:
        e: The exception that was raised
        errors: Optional error details
        level: Logging level to use
        warnings: Optional warning messages

    Returns:
        Flask Response with error details
    """
    exc = ForbiddenError(message=f"Unauthorized: {e}")
    return exc.make_error_response()


def handle_api_exception(e: ApiException) -> "Response":
    """Handle ApiException and its subclasses.

    Args:
        e: The API exception to handle

    Returns:
        Flask Response with error details
    """
    return e.make_error_response()


def handle_generic_exception(e: Exception) -> "Response":
    """Handle generic Python exceptions.

    Args:
        e: The exception to handle

    Returns:
        Flask Response with error details or original HTTP response
    """
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return make_response(e.get_response())

    api_exc = ApiInternalServerError(*e.args)
    return api_exc.make_error_response()


def handle_db_exception(e: DatabaseError) -> "Response":
    """Handle database exceptions.

    Automatically rolls back the database session before generating
    the error response.

    Args:
        e: The database error to handle

    Returns:
        Flask Response with error details
    """
    # Rollback the session:
    from ..sqla import db

    # Check that db was initialized
    if db.session is not None:
        db.session.rollback()
    api_exc = DBError(*e.args)
    return api_exc.make_error_response()


class RequestHandlers:
    """Handler class for registering error handlers with Flask.

    This class provides a simple way to register all error handlers
    with a Flask application.

    Example:
        >>> from flask import Flask
        >>> from flask_more_smorest.error import RequestHandlers
        >>>
        >>> app = Flask(__name__)
        >>> handlers = RequestHandlers(app)
    """

    def __init__(self, app: "Flask | None" = None) -> None:
        """Initialize request handlers.

        Args:
            app: Optional Flask application to register handlers with
        """
        if app is not None:
            self.init_app(app)

    def init_app(self, app: "Flask") -> None:
        """Register error handlers with Flask application.

        Args:
            app: Flask application to register handlers with
        """
        app.register_error_handler(ApiException, handle_api_exception)
        app.register_error_handler(DatabaseError, handle_db_exception)
        app.errorhandler(403)(unauthorized_handler)
        # TODO: debug 500 handlers
        app.errorhandler(500)(server_error_handler)
        app.register_error_handler(Exception, handle_generic_exception)
