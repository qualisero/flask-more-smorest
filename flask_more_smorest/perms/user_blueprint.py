"""User Blueprint with authentication endpoints."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

from flask_jwt_extended import create_access_token

from ..crud.crud_blueprint import CRUDMethod, MethodConfig, MethodConfigMapping
from ..error import UnauthorizedError
from .perms_blueprint import PermsBlueprint

if TYPE_CHECKING:
    from marshmallow import Schema

    from ..sqla.base_model import BaseModel
    from .models.abstract_user import AbstractUser


_user_bp: UserBlueprint | None = None


def _get_default_user_bp() -> UserBlueprint:
    """Get or create the default user_bp instance."""
    global _user_bp
    if _user_bp is None:
        _user_bp = UserBlueprint()
    return _user_bp


def __getattr__(name: str) -> UserBlueprint:
    """Lazy attribute access for default user_bp instance."""
    if name == "user_bp":
        return _get_default_user_bp()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class UserBlueprint(PermsBlueprint):
    """Blueprint for User CRUD operations with authentication endpoints.

    This blueprint extends CRUDBlueprint to provide:
    - Standard CRUD operations for User model (GET, POST, PATCH, DELETE)
    - Public login endpoint (POST /login/)
    - Current user profile endpoint (GET /me/)

    When the User model has PUBLIC_REGISTRATION=True, the POST endpoint is
    automatically made public to allow unauthenticated user registration.

    Args:
        name: Blueprint name (default: "users")
        import_name: Import name (default: __name__)
        model: Model class or string (default: User from registry)
        schema: Schema class or string (default: UserSchema)
        url_prefix: URL prefix for all routes (default: "/api/users/")
        methods: CRUD methods to enable (default: all methods)
        skip_methods: CRUD methods to disable (default: None)
        register: If True, register the model with init_fms (default: False)
        **kwargs: Additional arguments passed to CRUDBlueprint

    Example:
        >>> user_bp = UserBlueprint()
        >>> app.register_blueprint(user_bp)

        >>> # With custom configuration
        >>> user_bp = UserBlueprint(
        ...     url_prefix="/api/v2/users/",
        ...     skip_methods=[CRUDMethod.DELETE]
        ... )

        >>> # Register custom user model
        >>> user_bp = UserBlueprint(model=MyUser, register=True)

        >>> # Enable public registration
        >>> class PublicUser(User):
        ...     PUBLIC_REGISTRATION = True
        >>> public_bp = UserBlueprint(model=PublicUser)
    """

    def __init__(
        self,
        name: str = "users",
        import_name: str = __name__,
        model: type[BaseModel] | str | None = None,
        schema: type[Schema] | str | None = None,
        url_prefix: str | None = "/api/users/",
        methods: list[CRUDMethod] | MethodConfigMapping | None = None,
        skip_methods: list[CRUDMethod] | None = None,
        register: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize UserBlueprint with default User model and schema."""
        # Set defaults for model and schema
        if model is None:
            from .user_registry import get_user_model

            model = get_user_model()

        if schema is None:
            from .user_schemas import UserSchema

            schema = UserSchema

        # Register the model if requested
        if register and model is not None:
            from .user_registry import init_fms

            if not isinstance(model, type):
                raise TypeError("UserBlueprint register=True requires a model class")
            init_fms(user=cast("type[AbstractUser]", model))

        # Use default methods if not specified
        if methods is None:
            methods = list(CRUDMethod)

        # Check if PUBLIC_REGISTRATION is enabled on the model
        # If so, make the POST endpoint public
        public_registration = getattr(model, "PUBLIC_REGISTRATION", False)
        if public_registration and methods is not None:
            # Convert methods list to dict if needed to add public config
            if isinstance(methods, list):
                methods_dict: dict[CRUDMethod, MethodConfig | bool] = {m: {} for m in methods}
            else:
                methods_dict = dict(methods)
            # Mark POST as public (not requiring authentication)
            if CRUDMethod.POST in methods_dict:
                post_config = methods_dict[CRUDMethod.POST]
                if post_config is False:
                    pass  # POST is disabled, don't modify
                elif isinstance(post_config, dict):
                    post_config["public"] = True
                else:
                    methods_dict[CRUDMethod.POST] = {"public": True}
            methods = methods_dict

        super().__init__(
            name=name,
            import_name=import_name,
            model=model,
            schema=schema,
            url_prefix=url_prefix,
            methods=methods,
            skip_methods=skip_methods,
            **kwargs,
        )

        # Register additional user-specific endpoints
        self._register_login_endpoint()
        self._register_current_user_endpoint()

    def _validate_login(self, user: AbstractUser, data: dict[str, Any]) -> None:
        """Hook to add custom validation during login.

        Override this method in a subclass to add custom checks.
        Raise an exception (e.g., UnauthorizedError) if validation fails.

        Args:
            user: The user object attempting to login
            data: The login data (email, password)
        """
        pass

    def _register_login_endpoint(self) -> None:
        """Register the login endpoint."""
        from .models.abstract_user import AbstractUser
        from .user_schemas import TokenSchema, UserLoginSchema

        @self.public_endpoint
        @self.route("/login/", methods=["POST"])
        @self.arguments(UserLoginSchema)
        @self.response(HTTPStatus.OK, TokenSchema)
        def login(data: dict) -> dict[str, str]:
            """Login and get JWT token (public endpoint)."""

            user_model_cls: type[BaseModel] = self._config.model_cls

            # Make sure user_model_cls is a subclass of AbstractUser
            if not issubclass(user_model_cls, AbstractUser):
                raise UnauthorizedError("Invalid user model for login")

            # Use bypass_perms since this is a public endpoint without auth
            with user_model_cls.bypass_perms():
                user = user_model_cls.get_by(email=data["email"])

            if not user or not user.is_password_correct(data["password"]):
                raise UnauthorizedError("Invalid email or password")

            if not user.is_enabled:
                raise UnauthorizedError("Account is disabled")

            # Check domain access if domain is specified in login data
            if domain_name := data.get("domain"):
                from ..error.exceptions import NoDomainAccessError
                from .user_registry import get_domain_model

                # Get the registered Domain model
                Domain = get_domain_model()
                # Find domain by name (raises NotFoundError if not found)
                domain = Domain.get_by_or_404(name=domain_name)

                # Check if user has access to the domain
                if not user.has_domain_access(domain.id):
                    raise NoDomainAccessError()

            # Run custom validation hook
            self._validate_login(user, data)

            access_token = create_access_token(identity=user.id)

            return {"access_token": access_token, "token_type": "bearer"}

    def _register_current_user_endpoint(self) -> None:
        """Register the current user profile endpoint."""
        user_schema_cls: type[Schema] = self._config.schema_cls

        @self.route("/me/", methods=["GET"])
        @self.response(HTTPStatus.OK, user_schema_cls)
        def get_current_user_profile() -> AbstractUser:
            """Get current authenticated user's profile."""
            from .user_context import get_current_user

            user = get_current_user()
            if not user or not user.id:
                raise UnauthorizedError("Not authenticated")

            return user
