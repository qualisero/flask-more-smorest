"""Exception classes for Flask-More-Smorest API errors.

This module provides a hierarchy of exception classes for handling API errors,
with RFC 7807 Problem Details format, automatic logging, and debug information.

The error responses follow RFC 7807 (Problem Details for HTTP APIs):
https://datatracker.ietf.org/doc/html/rfc7807

Example response:
    {
        "type": "https://api.example.com/errors/not_found_error",
        "title": "Not Found",
        "status": 404,
        "detail": "User with id 123 doesn't exist",
        "instance": "/api/users/123"
    }
"""

import logging
import sys
import traceback
from http import HTTPStatus
from pprint import pformat
from typing import TYPE_CHECKING, Any

from flask import current_app, has_app_context, has_request_context, make_response, request

from ..utils import convert_camel_to_snake

if TYPE_CHECKING:
    from flask import Response

logger = logging.getLogger(__name__)


def _is_debug_mode() -> bool:
    """Check if Flask is running in debug or testing mode."""
    if not has_app_context():
        return False
    return current_app.debug or current_app.testing


def _get_error_type_uri(error_code: str) -> str:
    """Generate the RFC 7807 'type' URI for an error.

    Can be configured to point to actual documentation.
    Or use relative URI that could be used as error code.

    Args:
        error_code: The snake_case error code

    Returns:
        URI string for the error type
    """
    base_url = current_app.config.get("ERROR_TYPE_BASE_URL", "/errors") if has_app_context() else "/errors"
    return f"{base_url}/{error_code}"


class ApiException(Exception):
    """Base exception class for all API errors.

    This exception class provides automatic error response generation
    following RFC 7807 Problem Details format, along with logging and
    debug information collection.

    Attributes:
        TITLE: Human-readable error title (default: "Error")
        MESSAGE_PREFIX: Prefix for error messages (default: "")
        HTTP_STATUS_CODE: HTTP status code for the error (default: 500)
        INCLUDE_TRACEBACK: Whether to include traceback in response.
            Set to None to use environment-aware default (enabled in debug/testing).
            Set to True/False to override explicitly.
        debug_context: Additional context information for debugging

    Example:
        >>> class MyCustomError(ApiException):
        ...     TITLE = "Custom Error"
        ...     HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST
        >>> raise MyCustomError("Something went wrong")
    """

    TITLE = "Error"
    MESSAGE_PREFIX = ""
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    # None means use environment detection (debug/testing mode)
    # True/False explicitly enables/disables traceback
    INCLUDE_TRACEBACK: bool | None = None
    _debug_context: dict[str, str | int | bool | dict | None] | None = None
    _debug_context_kwargs: dict[str, str | int | bool | None]

    def __init__(
        self,
        message: str | None = None,
        **kwargs: str | int | bool | None,
    ) -> None:
        """Initialize the API exception.

        Args:
            message: Error message to display
            **kwargs: Additional context information
        """
        self.custom_args: dict[str, str | int | bool | None] = dict(kwargs)
        # Store kwargs for lazy evaluation
        self._debug_context_kwargs = dict(kwargs)
        self._debug_context = None  # Will be computed on first access

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

        super().__init__(self.message)

        self.log_exception()

    @property
    def debug_context(self) -> dict[str, str | int | bool | dict | None]:
        """Lazily compute debug context on first access.

        This property defers the expensive operation of collecting user context
        until the debug context is actually needed (typically only in debug mode
        when generating error responses).

        Returns:
            Dictionary containing debug context including user information
        """
        if self._debug_context is None:
            self._debug_context = self._compute_debug_context(**self._debug_context_kwargs)
        return self._debug_context

    def _compute_debug_context(self, **kwargs: str | int | bool | None) -> dict[str, str | int | bool | dict | None]:
        """Compute debug context (expensive operation).

        This method is only called when debug_context is actually accessed,
        avoiding unnecessary work in production.

        Args:
            **kwargs: Additional context information to include

        Returns:
            Dictionary containing debug context
        """
        return self.get_debug_context(**kwargs)

    @classmethod
    def error_code(cls) -> str:
        """Get the error code for this exception type.

        Returns:
            Snake-case error code derived from class name
        """
        return convert_camel_to_snake(cls.__name__)

    def get_debug_context(self, **kwargs: str | int | bool | None) -> dict[str, str | int | bool | dict | None]:
        """Get debugging context information.

        Collects user context via the configurable user context system, which works
        with both built-in and custom User models.

        Args:
            **kwargs: Additional context information to include

        Returns:
            Dictionary containing debug context including user information (in debug mode)
        """
        debug_context: dict[str, str | int | bool | dict | None] = dict()
        debug_context.update(kwargs)

        # Only collect user context in debug mode to avoid performance overhead
        if _is_debug_mode():
            from ..perms.user_context import get_current_user, get_current_user_id

            try:
                user_id = get_current_user_id()
                user = get_current_user()
                if user_id and user:
                    # Try to get roles if available (works with built-in User model)
                    roles: list[str] | None
                    if hasattr(user, "list_roles"):
                        roles = list(user.list_roles())
                    else:
                        raw_roles = getattr(user, "roles", None)
                        roles = [getattr(role, "role", role) for role in raw_roles] if raw_roles else None

                    debug_context["user"] = {
                        "id": str(user_id),
                        "roles": roles,
                    }
                else:
                    debug_context["user"] = {
                        "id": None,
                        "roles": None,
                        "msg": "Current user not authenticated",
                    }
            except Exception:
                debug_context["error"] = {"msg": "Error getting current user context"}

        return debug_context

    def _should_include_traceback(self) -> bool:
        """Determine if traceback should be included in the response.

        Uses class attribute if explicitly set, otherwise checks Flask
        debug/testing mode for environment-aware behavior.

        Returns:
            True if traceback should be included, False otherwise
        """
        if self.INCLUDE_TRACEBACK is not None:
            return self.INCLUDE_TRACEBACK
        return _is_debug_mode()

    def make_error_response(self) -> "Response":
        """Create an RFC 7807 Problem Details response.

        Returns a response following the RFC 7807 format:
        - type: URI identifying the error type
        - title: Human-readable title
        - status: HTTP status code
        - detail: Human-readable explanation
        - instance: URI of the resource (if in request context)

        In debug/testing mode, additional fields are included:
        - debug: Object containing traceback and context

        Returns:
            Flask Response object with problem details
        """
        problem: dict[str, Any] = {
            "type": _get_error_type_uri(self.error_code()),
            "title": self.TITLE,
            "status": int(self.HTTP_STATUS_CODE),
            "detail": self.message,
        }

        # Add instance URI if in request context
        if has_request_context():
            problem["instance"] = request.path

        # Include custom fields if provided
        if self.custom_args:
            problem["fields"] = self.custom_args

        # Only include debug information in debug/testing mode
        if _is_debug_mode():
            debug_info: dict[str, Any] = {
                "error_code": self.error_code(),
                "context": self.debug_context,
            }

            if self._should_include_traceback():
                exc = sys.exception()
                if exc is not None:
                    debug_info["traceback"] = traceback.format_list(traceback.extract_tb(exc.__traceback__))

            problem["debug"] = debug_info

        response = make_response(problem, self.HTTP_STATUS_CODE)
        response.content_type = "application/problem+json"
        return response

    def log_exception(self) -> None:
        """Log the exception with the appropriate level based on severity."""
        try:
            msg = f"{self.TITLE} ({self.error_code()}): {self.message}"
            if self.custom_args:
                msg += f"\n{pformat(self.custom_args)}"

            # Use structured logging with extra context
            extra: dict[str, Any] = {"error_code": self.error_code()}
            if _is_debug_mode():
                for k, v in self.debug_context.items():
                    extra[k] = v

            if self.HTTP_STATUS_CODE >= HTTPStatus.INTERNAL_SERVER_ERROR:
                logger.critical(msg, extra=extra, exc_info=True)
            elif self.HTTP_STATUS_CODE >= HTTPStatus.BAD_REQUEST:
                logger.warning(msg, extra=extra)
            else:
                logger.info(msg, extra=extra)
        except Exception as e:
            logger.critical(f"Error logging exception: {e}", exc_info=True)


# exception classes for generic handlers
class NotFoundError(ApiException):
    """404 Not Found error."""

    TITLE = "Not Found"
    HTTP_STATUS_CODE = HTTPStatus.NOT_FOUND


class ForbiddenError(ApiException):
    """403 Forbidden error with permission context.

    Provides detailed information about permission failures including
    the operation attempted, resource type, resource ID, and failure reason.

    Attributes:
        operation: Operation attempted (e.g., 'modify', 'create', 'delete')
        resource_type: Type of resource (e.g., 'Article', 'User')
        resource_id: ID of the specific resource
        reason: Human-readable reason for denial
    """

    TITLE = "Forbidden"
    HTTP_STATUS_CODE = HTTPStatus.FORBIDDEN

    def __init__(
        self,
        message: str | None = None,
        *,
        operation: str | None = None,
        resource_type: str | None = None,
        resource_id: Any = None,
        reason: str | None = None,
        **kwargs: str | int | bool | None,
    ) -> None:
        """Initialize ForbiddenError with permission context.

        Args:
            message: Error message (auto-generated if not provided)
            operation: Operation attempted (e.g., 'modify', 'create', 'delete')
            resource_type: Type of resource (e.g., 'Article', 'User')
            resource_id: ID of the specific resource
            reason: Human-readable reason for denial
            **kwargs: Additional debug_context information
        """
        self.operation = operation
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.reason = reason

        # Build detailed message if not provided
        if message is None and operation and resource_type:
            message = f"Cannot {operation} {resource_type}"
            if resource_id is not None:
                message += f" (id={resource_id})"
            if reason:
                message += f": {reason}"

        # Rollback database session
        from ..sqla import db

        if db.session:
            db.session.rollback()

        # Include permission context in debug_context
        if operation:
            kwargs["operation"] = operation
        if resource_type:
            kwargs["resource_type"] = resource_type
        if resource_id is not None:
            kwargs["resource_id"] = str(resource_id)
        if reason:
            kwargs["reason"] = reason

        super().__init__(message, **kwargs)


class UnauthorizedError(ApiException):
    """401 Unauthorized error."""

    TITLE = "Unauthorized"
    # Never include traceback for auth errors (security)
    INCLUDE_TRACEBACK = False
    HTTP_STATUS_CODE = HTTPStatus.UNAUTHORIZED


class BadRequestError(ApiException):
    """400 Bad Request error."""

    TITLE = "Bad Request"
    HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST


class ConflictError(ApiException):
    """409 Conflict error."""

    TITLE = "Conflict"
    HTTP_STATUS_CODE = HTTPStatus.CONFLICT


class UnprocessableEntity(ApiException):
    """422 Unprocessable Entity error for validation failures.

    This exception follows RFC 7807 with additional validation-specific fields:
    - errors: Object mapping locations to field errors

    Attributes:
        fields: Dictionary of field names to error messages
        location: Where the validation failed (json, query, file, etc.)
        valid_data: Data that passed validation (if any)
    """

    TITLE = "Validation Error"
    HTTP_STATUS_CODE = HTTPStatus.UNPROCESSABLE_ENTITY

    fields: dict[str, str]
    location: str | None
    valid_data: dict[str, str | int | bool] | None

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
            **kwargs: Additional debug_context information
        """
        self.fields = fields
        self.location = location
        self.valid_data = valid_data
        if message is None:
            message = "Invalid input data"
        super().__init__(message, **kwargs)

    def make_error_response(self) -> "Response":
        """Create an RFC 7807 response with validation errors.

        Extends the base Problem Details format with validation-specific fields:
        - errors: Object mapping location to field-level errors

        Returns:
            Flask Response object with validation error details
        """
        problem: dict[str, Any] = {
            "type": _get_error_type_uri(self.error_code()),
            "title": self.TITLE,
            "status": int(self.HTTP_STATUS_CODE),
            "detail": self.message,
            "errors": {self.location: {field: [msg] for field, msg in self.fields.items()}},
        }

        if has_request_context():
            problem["instance"] = request.path

        if _is_debug_mode() and self.debug_context:
            problem["debug"] = {"context": self.debug_context}

        response = make_response(problem, self.HTTP_STATUS_CODE)
        response.content_type = "application/problem+json"
        return response


class InternalServerError(ApiException):
    """500 Internal Server Error."""

    TITLE = "Internal Server Error"
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR

    def get_debug_context(self, **kwargs: str | int | bool | None) -> dict[str, str | int | bool | dict | None]:
        """Get debugging context including exception information.

        Args:
            **kwargs: Additional context information

        Returns:
            Dictionary with base context plus exception details
        """
        debug_context = super().get_debug_context(**kwargs)

        exc_type, exc_value, _exc_traceback = sys.exc_info()
        if exc_type is not None:
            debug_context["exception"] = {
                "type": str(exc_type.__name__),
                "value": str(exc_value),
            }
        return debug_context


class DBError(InternalServerError):
    """Database error (500 status code)."""

    TITLE = "Database Error"
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR


class NoDomainAccessError(ForbiddenError):
    """User does not have access to the requested domain."""

    TITLE = "Domain Access Denied"
    MESSAGE_PREFIX = "User does not have access to this domain."


class DomainNotFoundError(NotFoundError):
    """Requested domain was not found."""

    TITLE = "Domain Not Found"
    MESSAGE_PREFIX = "Domain not found."
