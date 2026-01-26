"""Type stubs for flask_more_smorest.perms module."""

from collections.abc import Callable
from typing import Any, TypeVar

# Import stubs for mixins
from .model_mixins import ProfileMixin, SoftDeleteMixin, TimestampMixin
from .models.abstract_role import AbstractDomain, AbstractUserRole
from .models.abstract_setting import AbstractUserSetting
from .models.abstract_token import AbstractToken

# Import abstract types for init_fms signature
from .models.abstract_user import AbstractUser

UserT = TypeVar("UserT")
RoleT = TypeVar("RoleT")
TokenT = TypeVar("TokenT")

# Blueprint classes
class UserBlueprint:
    """User blueprint for authentication."""
    def __init__(
        self,
        name: str = "users",
        import_name: str = ...,
        model: type[AbstractUser] | str | None = None,
        schema: type[Any] | str | None = None,
        url_prefix: str | None = "/api/users/",
        methods: list[Any] | None = None,
        skip_methods: list[Any] | None = None,
        register: bool = False,
        **kwargs: Any,
    ) -> None: ...
    def register_blueprint(self, blp: Any, **kwargs: Any) -> None: ...

# Registry functions
def init_fms(
    user: type[AbstractUser] | None = None,
    role: type[AbstractUserRole] | None = None,
    token: type[AbstractToken] | None = None,
    domain: type[AbstractDomain] | None = None,
    setting: type[AbstractUserSetting] | None = None,
    get_current_user: Callable[[], AbstractUser | None] | None = None,
) -> None: ...
def clear_registration() -> None: ...

# Type helper functions
def get_user_model(expected: type[UserT]) -> type[UserT]: ...
def get_role_model(expected: type[RoleT]) -> type[RoleT]: ...
def get_token_model(expected: type[TokenT]) -> type[TokenT]: ...
def get_domain_model(expected: type) -> type: ...
def get_setting_model(expected: type) -> type: ...

__all__ = [
    "ProfileMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UserBlueprint",
    "clear_registration",
    "init_fms",
]
