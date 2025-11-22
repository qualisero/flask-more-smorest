import logging
from http import HTTPStatus
import sys
from flask import make_response
from marshmallow import Schema, fields
import traceback
from pprint import pformat

from .database import db
from .utils import convert_camel_to_snake

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
    TITLE = "Error"
    MESSAGE_PREFIX = ""
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    # TODO: set to False in production
    INCLUDE_TRACEBACK = True
    context: dict = {}

    def __init__(
        self,
        message: str | None = None,
        exc: Exception | None = None,
        **kwargs: dict,
    ) -> None:
        self.custom_args = {}
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
    def error_code(cls):
        return convert_camel_to_snake(cls.__name__)

    def get_debug_context(self, **kwargs: dict) -> dict:
        from flask_jwt_extended import verify_jwt_in_request
        from .user import current_user

        context = dict()
        context.update(kwargs)

        try:
            if verify_jwt_in_request(optional=True):
                context["user"] = {"id": current_user.id, "roles": [r.role.name for r in current_user.roles]}
            else:
                context["user"] = {
                    "id": None,
                    "roles": None,
                    "msg": "Current user not authenticated",
                }
        except Exception:
            context["error"] = {"msg": "Error getting current user context"}

        return context

    def make_error_response(self):

        error = {
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
                formatted_tb = traceback.format_list(traceback.extract_tb(exc.__traceback__))
                error["debug"]["traceback"] = formatted_tb

        response_obj = {"error": ApiErrorResponseSchema().dump(error)}

        return make_response(response_obj, self.HTTP_STATUS_CODE)

    def log_exception(self):
        """Log the exception with the appropriate level."""

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
    HTTP_STATUS_CODE = HTTPStatus.NOT_FOUND


class ForbiddenError(ApiException):
    INCLUDE_TRACEBACK = True
    HTTP_STATUS_CODE = HTTPStatus.FORBIDDEN

    def __init__(self, message=None, **kwargs):
        db.session.rollback()
        super().__init__(message, **kwargs)


class UnauthorizedError(ApiException):
    INCLUDE_TRACEBACK = False
    HTTP_STATUS_CODE = HTTPStatus.UNAUTHORIZED


class BadRequestError(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST


class ConflictError(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.CONFLICT


class UnprocessableEntity(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.UNPROCESSABLE_ENTITY

    fields: dict[str, str] = {}
    location: str | None = None
    valid_data: dict[str, str] | None = None

    def __init__(
        self,
        fields: dict[str, str],
        location: str = "json",
        message: str | None = None,
        valid_data: dict[str, str] | None = None,
        **kwargs,
    ):
        """Initialize the UnprocessableEntity exception."""
        self.fields = fields
        self.location = location
        self.valid_data = valid_data
        if message is None:
            message = "Invalid input data"
        super().__init__(message, **kwargs)

    def make_error_response(self):
        """Create a response using Marshmallow's schema as model."""
        data = {
            "message": self.message,
            "errors": {self.location: {f: [v] for f, v in self.fields.items()}},
            "valid_data": self.valid_data,
        }
        response_obj = UnprocessableEntitySchema().dump(data)
        return make_response(response_obj, self.HTTP_STATUS_CODE)


class InternalServerError(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR

    def get_debug_context(self, **kwargs: dict) -> dict:
        context = super().get_debug_context(**kwargs)

        exc_type, exc_value, _exc_traceback = sys.exc_info()
        context["exception"] = {
            "type": str(exc_type),
            "value": str(exc_value),
            # "traceback": exc_traceback,
        }
        return context


class DBError(InternalServerError):
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    TITLE = "Database error"


class NoTenantAccessError(ForbiddenError):
    TITLE = "Wrong tenant"
    MESSAGE_PREFIX = "User does not have access to this tenant."


class TenantNotFoundError(NotFoundError):
    TITLE = "Tenant not found"
    MESSAGE_PREFIX = "Tenant not found."
