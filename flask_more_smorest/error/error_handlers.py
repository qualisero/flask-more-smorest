"""Error handlers for Flask-More-Smorest.

This module provides error handler functions and a RequestHandlers class
for registering error handlers with Flask applications.
"""

import contextlib
import logging
from typing import TYPE_CHECKING

from flask import make_response
from sqlalchemy.exc import DatabaseError, IntegrityError
from werkzeug.exceptions import HTTPException

from .exceptions import ApiException, DBError, ForbiddenError
from .exceptions import InternalServerError as ApiInternalServerError
from .exceptions import _is_debug_mode as _is_debug_mode  # pyright: ignore[reportPrivateUsage]
from .integrity import GENERIC_DB_ERROR_MESSAGE, parse_integrity_error, to_api_exception

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
    e: Exception,
    errors: dict[str, str] | None = None,
    level: str = "info",
    warnings: list[str] | None = None,
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

    # Never echo raw exception text (it may embed SQL statements and
    # parameter values) outside debug/testing mode.
    if _is_debug_mode():
        api_exc = ApiInternalServerError(*e.args)
    else:
        api_exc = ApiInternalServerError("An internal error occurred.")
    return api_exc.make_error_response()


def _rollback_session() -> None:
    """Roll back the current database session, if the database is initialized."""
    # inline: avoids the error <-> sqla import cycle
    from ..sqla import db

    # db.session raises RuntimeError when init_db was never run. Never mask the
    # original database error with that.
    with contextlib.suppress(RuntimeError):
        db.session.rollback()


def handle_integrity_error(e: IntegrityError) -> "Response":
    """Handle database integrity errors with structured, safe responses.

    Rolls back the session, then translates the constraint violation into an
    :class:`~flask_more_smorest.error.exceptions.IntegrityConflict` (422),
    :class:`~flask_more_smorest.error.exceptions.ResourceInUse` (409) or a
    sanitised :class:`~flask_more_smorest.error.exceptions.DBError` (500).
    See :mod:`flask_more_smorest.error.integrity`.

    Args:
        e: The integrity error to handle

    Returns:
        Flask Response with error details
    """
    _rollback_session()

    # Expected outcome of user input, not a server fault: log without traceback,
    # and without str(e), which embeds the SQL statement and bound parameter
    # values. The full detail is available at DEBUG level.
    violation = parse_integrity_error(e)
    if violation is not None:
        logger.warning(
            "Integrity violation: kind=%s table=%s columns=%s",
            violation.kind,
            violation.table,
            ",".join(violation.columns),
        )
    else:
        logger.warning(
            "Unparseable integrity error (%s)",
            type(e.orig).__name__ if e.orig is not None else "no orig",
        )
    logger.debug("Integrity error detail: %s", e)
    return to_api_exception(e).make_error_response()


def handle_db_exception(e: DatabaseError) -> "Response":
    """Handle database exceptions.

    Automatically rolls back the database session before generating
    the error response.

    Args:
        e: The database error to handle

    Returns:
        Flask Response with error details
    """
    _rollback_session()

    # No str(e) in the message: it embeds SQL and bound parameter values. The
    # traceback (which ends with the same text) is retained deliberately —
    # genuine database faults are rare and need full context for diagnosis.
    logger.exception("Database error")
    # Never echo the driver's error text (SQL statement and parameter values)
    # outside debug/testing mode.
    api_exc = DBError(*e.args) if _is_debug_mode() else DBError(GENERIC_DB_ERROR_MESSAGE)
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
        # Flask resolves handlers over type(e).__mro__, so the more specific
        # IntegrityError handler wins and DatabaseError catches everything else.
        app.register_error_handler(IntegrityError, handle_integrity_error)
        app.register_error_handler(DatabaseError, handle_db_exception)
        app.errorhandler(403)(unauthorized_handler)
        # TODO: debug 500 handlers
        app.errorhandler(500)(server_error_handler)
        app.register_error_handler(Exception, handle_generic_exception)
