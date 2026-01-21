"""User schemas."""

from marshmallow import fields, pre_load

from ..sqla.base_model import BaseSchema
from .models import User


class UserSchema(User.Schema):
    """Public user schema - extends auto-generated schema."""

    password = fields.Str(required=True, load_only=True)


class UserLoginSchema(UserSchema):
    """Schema for user login."""

    class Meta:
        fields = ("email", "password")

    @pre_load
    def normalize_email(self, data: dict, **kwargs: object) -> dict:
        """Normalize email to lowercase for case-insensitive login."""
        if "email" in data and data["email"]:
            data["email"] = data["email"].lower()
        return data


class TokenSchema(BaseSchema):
    """Schema for JWT token response."""

    access_token = fields.Str(required=True)
    token_type = fields.Str(dump_default="bearer")
