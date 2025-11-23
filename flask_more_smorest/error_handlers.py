import werkzeug
import logging

from sqlalchemy.exc import DatabaseError
from flask import Flask
from werkzeug.exceptions import HTTPException, InternalServerError

from .exceptions import InternalServerError, ApiException, ForbiddenError, DBError

logger = logging.getLogger(__name__)


def server_error_handler(e):
    exc = InternalServerError(message=f"Unhandled Exception: {e}")

    logger.critical(
        "Encountered Unhandled Exception!",
        extra=exc.get_debug_context(),
    )

    return exc.make_error_response()


def unauthorized_handler(e, errors=None, level="info", warnings=None):
    exc = ForbiddenError(message=f"Unauthorized: {e}")
    return exc.make_error_response()


def handle_api_exception(e: ApiException):
    return e.make_error_response()


def handle_generic_exception(e: Exception):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e.get_response()

    api_exc = InternalServerError(*e.args)
    return api_exc.make_error_response()


def handle_db_exception(e: DatabaseError):
    # Rollback the session:
    from .database import db

    db.session.rollback()
    api_exc = DBError(*e.args)
    return api_exc.make_error_response()


class RequestHandlers:
    def __init__(self, app=None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        app.register_error_handler(ApiException, handle_api_exception)
        app.register_error_handler(DatabaseError, handle_db_exception)
        app.errorhandler(403)(unauthorized_handler)
        # TODO: debug 500 handlers
        app.errorhandler(500)(server_error_handler)
        app.register_error_handler(Exception, handle_generic_exception)
