"""Exception classes for Flask-More-Smorest API errors.

This module provides a hierarchy of exception classes for handling API errors,
with automatic logging, debug information, and standardized error responses.
"""

import logging
from http import HTTPStatus
import sys
from typing import TYPE_CHECKING
from flask import make_response
from marshmallow import Schema, fields
import traceback
from pprint import pformat

from ..utils import convert_camel_to_snake

if TYPE_CHECKING:
    from flask import Response

logger = logging.getLogger(__name__)


class ApiErrorDebugSchema(Schema):
    message = fields.String(required=True)
    traceback = fields.List(fields.String)
    context = fields.Dict()


class ApiErrorResponseSchema(Schema):
    title = fields.String(required=True)
    status_code = fields.Integer(required=True)
    error_code = fields.String(required=True)
    details = fields.Dict(dump_default={})
    debug = fields.Nested(ApiErrorDebugSchema, required=True)


class UnprocessableEntityError(Schema):
    """Schema for unprocessable entity errors."""

    json = fields.Dict(required=False)
    file = fields.Dict(required=False)
    query = fields.Dict(required=False)


class UnprocessableEntitySchema(Schema):
    """Schema for unprocessable entity exception."""

    message = fields.String(required=True)
    errors = fields.Nested(UnprocessableEntityError, required=True)
    valid_data = fields.Dict(required=False)


class ApiException(Exception):
    """Base exception class for all API errors.

    This exception class provides automatic error response generation,
    logging, and debug information collection. All custom API exceptions
    should inherit from this class.

    Attributes:
        TITLE: Human-readable error title (default: "Error")
        MESSAGE_PREFIX: Prefix for error messages (default: "")
        HTTP_STATUS_CODE: HTTP status code for the error (default: 500)
        INCLUDE_TRACEBACK: Whether to include traceback in response (default: True)
        context: Additional context information for debugging

    Example:
        >>> class MyCustomError(ApiException):
        ...     TITLE = "Custom Error"
        ...     HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST
        >>> raise MyCustomError("Something went wrong")
    """

    TITLE = "Error"
    MESSAGE_PREFIX = ""
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    # TODO: set to False in production
    INCLUDE_TRACEBACK = True
    context: dict[str, str | int | bool | dict | None] = {}

    def __init__(
        self,
        message: str | None = None,
        exc: Exception | None = None,
        **kwargs: str | int | bool | None,
    ) -> None:
        """Initialize the API exception.

        Args:
            message: Error message to display
            exc: Original exception that caused this error
            **kwargs: Additional context information
        """
        self.custom_args: dict[str, str | int | bool | None] = {}
        self.context = self.get_debug_context(**kwargs)

        if message is None:
            if self.MESSAGE_PREFIX:
                self.message = self.MESSAGE_PREFIX
            else:
                self.message = f"Exception: {self}"
        else:
            if self.MESSAGE_PREFIX:
                self.message = f"{self.MESSAGE_PREFIX}: {message}"
            else:
                self.message = message

        super().__init__(self.message, **kwargs)

        self.log_exception()

    @classmethod
    def error_code(cls) -> str:
        """Get the error code for this exception type.

        Returns:
            Snake-case error code derived from class name
        """
        return convert_camel_to_snake(cls.__name__)

    def get_debug_context(self, **kwargs: str | int | bool | None) -> dict[str, str | int | bool | dict | None]:
        """Get debugging context information.

        Args:
            **kwargs: Additional context information to include

        Returns:
            Dictionary containing debug context including user information
        """
        context: dict[str, str | int | bool | dict | None] = dict()
        context.update(kwargs)

        if True:  # TODO: check if auth is enabled
            from ..perms import get_current_user_id, current_user

            try:
                if user_id := get_current_user_id():
                    context["user"] = {"id": user_id, "roles": [r.role for r in current_user.roles]}
                else:
                    context["user"] = {
                        "id": None,
                        "roles": None,
                        "msg": "Current user not authenticated",
                    }
            except Exception:
                context["error"] = {"msg": "Error getting current user context"}

        return context

    def make_error_response(self) -> "Response":
        """Create a Flask response object for this error.

        Returns:
            Flask Response object with error details and appropriate status code
        """

        error: dict[str, str | int | dict] = {
            "status_code": self.HTTP_STATUS_CODE,
            "title": self.TITLE,
            "error_code": self.error_code(),
            "details": self.custom_args,
            "debug": {
                "message": self.message,
                # TODO hide traceback on production?
                "context": self.context,
            },
        }

        if self.INCLUDE_TRACEBACK:
            exc = sys.exception()
            if exc is not None:
                formatted_tb: list[str] = traceback.format_list(traceback.extract_tb(exc.__traceback__))
                error["debug"]["traceback"] = formatted_tb

        response_obj: dict[str, dict] = {"error": ApiErrorResponseSchema().dump(error)}

        return make_response(response_obj, self.HTTP_STATUS_CODE)

    def log_exception(self) -> None:
        """Log the exception with the appropriate level based on severity."""

        try:
            msg = f"{self.TITLE} ({self.error_code()}): {self.message}"
            if len(self.custom_args):
                msg += f"\n{pformat(self.custom_args)}"

            if self.HTTP_STATUS_CODE >= HTTPStatus.INTERNAL_SERVER_ERROR:
                logger.critical(msg, extra=self.context, exc_info=True)
            elif self.HTTP_STATUS_CODE >= HTTPStatus.BAD_REQUEST:
                logger.warning(msg, extra=self.context)
            else:
                logger.info(msg, extra=self.context)
        except Exception as e:
            logger.critical(f"Error logging exception: {e}", exc_info=True)


# exception classes for generic handlers
class NotFoundError(ApiException):
    """404 Not Found error."""

    HTTP_STATUS_CODE = HTTPStatus.NOT_FOUND


class ForbiddenError(ApiException):
    """403 Forbidden error with automatic session rollback."""

    INCLUDE_TRACEBACK = True
    HTTP_STATUS_CODE = HTTPStatus.FORBIDDEN

    def __init__(self, message: str | None = None, **kwargs: str | int | bool | None) -> None:
        """Initialize ForbiddenError and rollback database session.

        Args:
            message: Error message
            **kwargs: Additional context information
        """
        from ..sqla import db

        if db.session:
            db.session.rollback()
        super().__init__(message, **kwargs)


class UnauthorizedError(ApiException):
    """401 Unauthorized error."""

    INCLUDE_TRACEBACK = False
    HTTP_STATUS_CODE = HTTPStatus.UNAUTHORIZED


class BadRequestError(ApiException):
    """400 Bad Request error."""

    HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST


class ConflictError(ApiException):
    """409 Conflict error."""

    HTTP_STATUS_CODE = HTTPStatus.CONFLICT


class UnprocessableEntity(ApiException):
    """422 Unprocessable Entity error for validation failures.

    This exception is used for request validation errors, typically
    from Marshmallow schema validation.

    Attributes:
        fields: Dictionary of field names to error messages
        location: Where the validation failed (json, query, file, etc.)
        valid_data: Data that passed validation (if any)
    """

    HTTP_STATUS_CODE = HTTPStatus.UNPROCESSABLE_ENTITY

    fields: dict[str, str] = {}
    location: str | None = None
    valid_data: dict[str, str | int | bool] | None = None

    def __init__(
        self,
        fields: dict[str, str],
        location: str = "json",
        message: str | None = None,
        valid_data: dict[str, str | int | bool] | None = None,
        **kwargs: str | int | bool | None,
    ) -> None:
        """Initialize the UnprocessableEntity exception.

        Args:
            fields: Dictionary mapping field names to error messages
            location: Where the error occurred (default: "json")
            message: Overall error message (default: "Invalid input data")
            valid_data: Data that passed validation
            **kwargs: Additional context information
        """
        self.fields = fields
        self.location = location
        self.valid_data = valid_data
        if message is None:
            message = "Invalid input data"
        super().__init__(message, **kwargs)

    def make_error_response(self) -> "Response":
        """Create a response using Marshmallow's schema as model.

        Returns:
            Flask Response object with validation error details
        """
        data: dict[str, str | dict] = {
            "message": self.message,
            "errors": {self.location: {f: [v] for f, v in self.fields.items()}},
            "valid_data": self.valid_data,
        }
        response_obj: dict[str, str | dict] = UnprocessableEntitySchema().dump(data)
        return make_response(response_obj, self.HTTP_STATUS_CODE)


class InternalServerError(ApiException):
    """500 Internal Server Error."""

    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR

    def get_debug_context(self, **kwargs: str | int | bool | None) -> dict[str, str | int | bool | dict | None]:
        """Get debugging context including exception information.

        Args:
            **kwargs: Additional context information

        Returns:
            Dictionary with base context plus exception details
        """
        context = super().get_debug_context(**kwargs)

        exc_type, exc_value, _exc_traceback = sys.exc_info()
        context["exception"] = {
            "type": str(exc_type),
            "value": str(exc_value),
            # "traceback": exc_traceback,
        }
        return context


class DBError(InternalServerError):
    """Database error (500 status code)."""

    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    TITLE = "Database error"


class NoTenantAccessError(ForbiddenError):
    """User does not have access to the requested tenant."""

    TITLE = "Wrong tenant"
    MESSAGE_PREFIX = "User does not have access to this tenant."


class TenantNotFoundError(NotFoundError):
    """Requested tenant was not found."""

    TITLE = "Tenant not found"
    MESSAGE_PREFIX = "Tenant not found."
