"""User model registry for Flask-More-Smorest.

Provides a single registry for all user-related models, serving as the
canonical integration point for the permissions system.

**Quick Start:**

    # Use all default models (no imports needed)
    from flask_more_smorest.perms import init_fms
    init_fms()

    # Or register custom user model with defaults for others
    from flask_more_smorest.perms import init_fms
    from myapp.models import User
    init_fms(user=User)

    # Or register all models explicitly
    from flask_more_smorest.perms import init_fms
    from myapp.models import User, UserRole, Token, Domain, UserSetting
    init_fms(
        user=User,
        role=UserRole,
        token=Token,
        domain=Domain,
        setting=UserSetting,
    )

**Resolution Order:**
1. Explicitly registered model
2. Default model (auto-loaded by init_fms)
3. Error (model not registered)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar, cast, overload

from flask import has_app_context

if TYPE_CHECKING:
    from .models.abstract_role import AbstractDomain, AbstractUserRole
    from .models.abstract_setting import AbstractUserSetting
    from .models.abstract_token import AbstractToken
    from .models.abstract_user import AbstractUser

    # Type for user context function
    GetCurrentUserFunc = Callable[[], AbstractUser | None]
else:  # pragma: no cover - runtime placeholder
    AbstractUser = object  # type: ignore[assignment,misc]
    AbstractUserRole = object  # type: ignore[assignment,misc]
    AbstractToken = object  # type: ignore[assignment,misc]
    AbstractDomain = object  # type: ignore[assignment,misc]
    AbstractUserSetting = object  # type: ignore[assignment,misc]
    GetCurrentUserFunc = Callable[[], object | None]  # type: ignore[assignment,misc]

UserT = TypeVar("UserT", bound="AbstractUser")
RoleT = TypeVar("RoleT", bound="AbstractUserRole")
TokenT = TypeVar("TokenT", bound="AbstractToken")
DomainT = TypeVar("DomainT", bound="AbstractDomain")
SettingT = TypeVar("SettingT", bound="AbstractUserSetting")

# Registry storage
_USER_REGISTRY_STATE_KEY = "user_registry"


def _get_app_state() -> dict:
    """Get app state from Flask extensions.

    Syncs with global state to ensure consistency when init_fms() is called
    outside an app context but models are accessed inside one (e.g., in tests).
    """
    from flask import current_app

    extensions_state = current_app.extensions.setdefault("flask-more-smorest", {})

    # Get or create app state with initial values from global state
    app_state = extensions_state.setdefault(
        _USER_REGISTRY_STATE_KEY,
        {
            "user_model": _user_model,
            "role_model": _role_model,
            "token_model": _token_model,
            "domain_model": _domain_model,
            "setting_model": _setting_model,
            "get_current_user_func": _get_current_user_func,
            "models_initialized": _models_initialized,
            "helpers_initialized": _helpers_initialized,
        },
    )

    # Sync from global if app state is uninitialized but global is initialized
    # This handles case where init_fms() was called without app context,
    # then app state was cleared (in tests), and now accessed with app context
    if not app_state.get("models_initialized") and _models_initialized:
        app_state["user_model"] = _user_model
        app_state["role_model"] = _role_model
        app_state["token_model"] = _token_model
        app_state["domain_model"] = _domain_model
        app_state["setting_model"] = _setting_model
        app_state["get_current_user_func"] = _get_current_user_func
        app_state["models_initialized"] = _models_initialized
        app_state["helpers_initialized"] = _helpers_initialized

    return cast(dict, app_state)


def _get_state() -> tuple[dict, bool]:
    """Get registry state, returning (state_dict, is_app_state)."""
    if has_app_context():
        return _get_app_state(), True

    return {
        "user_model": _user_model,
        "role_model": _role_model,
        "token_model": _token_model,
        "domain_model": _domain_model,
        "setting_model": _setting_model,
        "get_current_user_func": _get_current_user_func,
        "models_initialized": _models_initialized,
        "helpers_initialized": _helpers_initialized,
    }, False


# Global fallback (when no app context)
_user_model: type[AbstractUser] | None = None
_role_model: type[AbstractUserRole] | None = None
_token_model: type[AbstractToken] | None = None
_domain_model: type[AbstractDomain] | None = None
_setting_model: type[AbstractUserSetting] | None = None
_get_current_user_func: GetCurrentUserFunc | None = None
_models_initialized = False
_helpers_initialized = False


def init_fms(
    user: type[AbstractUser] | None = None,
    role: type[AbstractUserRole] | None = None,
    token: type[AbstractToken] | None = None,
    domain: type[AbstractDomain] | None = None,
    setting: type[AbstractUserSetting] | None = None,
    get_current_user: Callable[[], AbstractUser | None] | None = None,
) -> None:
    """Initialize Flask-More-Smorest perms integration.

    This is the primary integration point. It registers models and helper
    functions in a single call. Missing models are filled with defaults.

    The first call initializes models + helpers. Later calls may only
    update helper functions (model changes are rejected).
    """
    state, is_app_state = _get_state()
    models_initialized = bool(state.get("models_initialized", False))

    if models_initialized and any(model is not None for model in (user, role, token, domain, setting)):
        current = {
            "user": state.get("user_model"),
            "role": state.get("role_model"),
            "token": state.get("token_model"),
            "domain": state.get("domain_model"),
            "setting": state.get("setting_model"),
        }
        requested = {
            "user": user,
            "role": role,
            "token": token,
            "domain": domain,
            "setting": setting,
        }
        mismatched = {
            key: (requested[key], current[key])
            for key in current
            if requested[key] is not None and requested[key] is not current[key]
        }
        if mismatched:
            raise RuntimeError("Models are already initialized. Call init_fms(get_current_user=...) to update helpers.")

    if not models_initialized:
        # Import abstract bases for type checking
        from .models.abstract_role import AbstractDomain, AbstractUserRole
        from .models.abstract_setting import AbstractUserSetting
        from .models.abstract_token import AbstractToken
        from .models.abstract_user import AbstractUser

        # Import defaults only for models that weren't provided
        # IMPORTANT: Don't import ANY default if user is provided, to avoid
        # having both CustomUser and default User in the same registry
        if user is not None:
            # Fill in None values with defaults but don't import User
            if role is None:
                from .models.defaults import UserRole

                role = UserRole
            if token is None:
                from .models.defaults import Token

                token = Token
            if domain is None:
                from .models.defaults import Domain

                domain = Domain
            if setting is None:
                from .models.defaults import UserSetting

                setting = UserSetting
        else:
            # Import all defaults
            from .models.defaults import (
                Domain,
                Token,
                User,
                UserRole,
                UserSetting,
            )

            user = User
            role = UserRole if role is None else role
            token = Token if token is None else token
            domain = Domain if domain is None else domain
            setting = UserSetting if setting is None else setting

        # Type checking - AbstractUser and related already imported above
        if not issubclass(user, AbstractUser):
            raise TypeError(f"user must be a subclass of AbstractUser, got {user}")
        if not issubclass(role, AbstractUserRole):
            raise TypeError(f"role must be a subclass of AbstractUserRole, got {role}")
        if not issubclass(token, AbstractToken):
            raise TypeError(f"token must be a subclass of AbstractToken, got {token}")
        if not issubclass(domain, AbstractDomain):
            raise TypeError(f"domain must be a subclass of AbstractDomain, got {domain}")
        if not issubclass(setting, AbstractUserSetting):
            raise TypeError(f"setting must be a subclass of AbstractUserSetting, got {setting}")

        # Validate User model tablename for compatibility with HasUserMixin foreign keys
        if hasattr(user, "__tablename__") and user.__tablename__ != "user":
            import warnings

            warnings.warn(
                f"User model uses __tablename__ = '{user.__tablename__}' instead of 'user'. "
                f"This may cause issues with default Domain/UserRole/Token/UserSetting models. "
                f"Consider using __tablename__ = 'user' or providing custom implementations for all models.",
                UserWarning,
                stacklevel=2,
            )

        state["user_model"] = user
        state["role_model"] = role
        state["token_model"] = token
        state["domain_model"] = domain
        state["setting_model"] = setting
        state["models_initialized"] = True

    if get_current_user is not None:
        state["get_current_user_func"] = get_current_user
        state["helpers_initialized"] = True

    if not is_app_state:
        global _user_model, _role_model, _token_model, _domain_model, _setting_model, _get_current_user_func
        global _models_initialized, _helpers_initialized
        _user_model = state["user_model"]
        _role_model = state["role_model"]
        _token_model = state["token_model"]
        _domain_model = state["domain_model"]
        _setting_model = state["setting_model"]
        _get_current_user_func = state["get_current_user_func"]
        _models_initialized = bool(state.get("models_initialized", False))
        _helpers_initialized = bool(state.get("helpers_initialized", False))


def ensure_models_initialized() -> None:
    """Ensure init_fms has registered models before mapper configuration."""
    state, _ = _get_state()
    if not state.get("models_initialized", False):
        raise RuntimeError(
            "init_fms() must be called before SQLAlchemy mapper configuration. "
            "Initialize flask-more-smorest perms in your app factory before db.create_all()."
        )


@overload
def get_user_model(expected: type[UserT]) -> type[UserT]: ...


@overload
def get_user_model(expected: None = None) -> type[AbstractUser]: ...


def get_user_model(expected: type[UserT] | None = None) -> type[UserT] | type[AbstractUser]:
    """Get the registered User model class.

    Args:
        expected: Optional expected User subclass for typed return.

    Returns:
        Registered User model class

    Raises:
        RuntimeError: If no User model is registered or expected doesn't match.
    """
    state, _ = _get_state()

    if state["user_model"] is not None:
        model = cast("type[AbstractUser]", state["user_model"])
        if expected is not None and model is not expected:
            raise RuntimeError("Registered User model does not match expected type")
        return cast("type[UserT]", model) if expected is not None else model

    raise RuntimeError("No User model registered. Call init_fms(...) before using perms models.")


@overload
def get_role_model(expected: type[RoleT]) -> type[RoleT]: ...


@overload
def get_role_model(expected: None = None) -> type[AbstractUserRole]: ...


def get_role_model(expected: type[RoleT] | None = None) -> type[RoleT] | type[AbstractUserRole]:
    """Get the registered UserRole model class.

    Args:
        expected: Optional expected UserRole subclass for typed return.

    Returns:
        Registered UserRole model class

    Raises:
        RuntimeError: If no UserRole model is registered or expected doesn't match.
    """
    state, _ = _get_state()

    if state["role_model"] is not None:
        model = cast("type[AbstractUserRole]", state["role_model"])
        if expected is not None and model is not expected:
            raise RuntimeError("Registered UserRole model does not match expected type")
        return cast("type[RoleT]", model) if expected is not None else model

    raise RuntimeError("No UserRole model registered. Call init_fms(...) before using perms models.")


@overload
def get_token_model(expected: type[TokenT]) -> type[TokenT]: ...


@overload
def get_token_model(expected: None = None) -> type[AbstractToken]: ...


def get_token_model(expected: type[TokenT] | None = None) -> type[TokenT] | type[AbstractToken]:
    """Get the registered Token model class.

    Args:
        expected: Optional expected Token subclass for typed return.

    Returns:
        Registered Token model class

    Raises:
        RuntimeError: If no Token model is registered or expected doesn't match.
    """
    state, _ = _get_state()

    if state["token_model"] is not None:
        model = cast("type[AbstractToken]", state["token_model"])
        if expected is not None and model is not expected:
            raise RuntimeError("Registered Token model does not match expected type")
        return cast("type[TokenT]", model) if expected is not None else model

    raise RuntimeError("No Token model registered. Call init_fms(...) before using perms models.")


@overload
def get_domain_model(expected: type[DomainT]) -> type[DomainT]: ...


@overload
def get_domain_model(expected: None = None) -> type[AbstractDomain]: ...


def get_domain_model(expected: type[DomainT] | None = None) -> type[DomainT] | type[AbstractDomain]:
    """Get the registered Domain model class.

    Args:
        expected: Optional expected Domain subclass for typed return.

    Returns:
        Registered Domain model class

    Raises:
        RuntimeError: If no Domain model is registered or expected doesn't match.
    """
    state, _ = _get_state()

    if state["domain_model"] is not None:
        model = cast("type[AbstractDomain]", state["domain_model"])
        if expected is not None and model is not expected:
            raise RuntimeError("Registered Domain model does not match expected type")
        return cast("type[DomainT]", model) if expected is not None else model

    raise RuntimeError("No Domain model registered. Call init_fms(...) before using perms models.")


@overload
def get_setting_model(expected: type[SettingT]) -> type[SettingT]: ...


@overload
def get_setting_model(expected: None = None) -> type[AbstractUserSetting]: ...


def get_setting_model(expected: type[SettingT] | None = None) -> type[SettingT] | type[AbstractUserSetting]:
    """Get the registered UserSetting model class.

    Args:
        expected: Optional expected UserSetting subclass for typed return.

    Returns:
        Registered UserSetting model class

    Raises:
        RuntimeError: If no UserSetting model is registered or expected doesn't match.
    """
    state, _ = _get_state()

    if state["setting_model"] is not None:
        model = cast("type[AbstractUserSetting]", state["setting_model"])
        if expected is not None and model is not expected:
            raise RuntimeError("Registered UserSetting model does not match expected type")
        return cast("type[SettingT]", model) if expected is not None else model

    raise RuntimeError("No UserSetting model registered. Call init_fms(...) before using perms models.")


def expect_user_model(expected: type[UserT]) -> type[UserT]:
    """Return the registered User model and enforce the expected type."""
    return get_user_model(expected)


def expect_role_model(expected: type[RoleT]) -> type[RoleT]:
    """Return the registered UserRole model and enforce the expected type."""
    return get_role_model(expected)


def expect_token_model(expected: type[TokenT]) -> type[TokenT]:
    """Return the registered Token model and enforce the expected type."""
    return get_token_model(expected)


def expect_domain_model(expected: type[DomainT]) -> type[DomainT]:
    """Return the registered Domain model and enforce the expected type."""
    return get_domain_model(expected)


def expect_setting_model(expected: type[SettingT]) -> type[SettingT]:
    """Return the registered UserSetting model and enforce the expected type."""
    return get_setting_model(expected)


def get_current_user_func() -> Callable[[], AbstractUser | None] | None:
    """Get the registered get_current_user function.

    Returns:
        Registered function or None
    """
    state, _ = _get_state()
    return cast("Callable[[], AbstractUser | None] | None", state.get("get_current_user_func"))


def clear_registration() -> None:
    """Clear all registered user models and custom getter.

    Resets the registry to its initial state, forcing fallback to defaults
    (if imported). Useful for testing.

    Example:

    .. code-block:: python

        def test_with_custom_user():
            init_fms(user=MyUser)
            # ... test ...
            clear_registration()  # Reset for next test
    """
    state, is_app_state = _get_state()

    state["user_model"] = None
    state["role_model"] = None
    state["token_model"] = None
    state["domain_model"] = None
    state["setting_model"] = None
    state["get_current_user_func"] = None
    state["models_initialized"] = False
    state["helpers_initialized"] = False

    global _user_model, _role_model, _token_model, _domain_model, _setting_model, _get_current_user_func
    global _models_initialized, _helpers_initialized
    _user_model = None
    _role_model = None
    _token_model = None
    _domain_model = None
    _setting_model = None
    _get_current_user_func = None
    _models_initialized = False
    _helpers_initialized = False
