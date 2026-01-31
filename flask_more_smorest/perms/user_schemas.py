"""User schemas."""

from typing import TYPE_CHECKING, Any

from marshmallow import fields, pre_load

from ..sqla.base_model import BaseSchema
from .user_registry import get_user_model

if TYPE_CHECKING:

    class BaseUserSchema(BaseSchema):
        pass
else:
    BaseUserSchema = get_user_model().Schema


class UserSchema(BaseUserSchema):
    """Public user schema - extends auto-generated schema."""

    password = fields.Str(required=True, load_only=True)


class UserLoginSchema(UserSchema):
    """Schema for user login."""

    domain = fields.Str(required=False, load_default=None)

    class Meta:
        fields = ("email", "password", "domain")

    @pre_load
    def normalize_email(self, data: dict[str, Any], **kwargs: object) -> dict[str, Any]:
        """Normalize email to lowercase for case-insensitive login."""
        if data.get("email"):
            data["email"] = data["email"].lower()
        return data


class TokenSchema(BaseSchema):
    """Schema for JWT token response."""

    access_token = fields.Str(required=True)
    token_type = fields.Str(dump_default="bearer")
