"""Flask-More-Smorest Extensions.

A powerful extension library for Flask-Smorest that provides automatic CRUD operations,
enhanced blueprints with annotations, advanced query filtering capabilities, and
extensible user management with custom model support.

Quick Start Example:
    >>> from flask import Flask
    >>> from flask_more_smorest import BaseModel, CRUDBlueprint, init_db
    >>> from flask_more_smorest.perms import Api
    >>> from flask_more_smorest.sqla import db
    >>> from sqlalchemy.orm import Mapped, mapped_column
    >>>
    >>> app = Flask(__name__)
    >>> app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    >>>
    >>> class Product(BaseModel):
    ...     name: Mapped[str] = mapped_column(db.String(100))
    ...     price: Mapped[float] = mapped_column(db.Float)
    >>>
    >>> init_db(app)
    >>> api = Api(app)
    >>>
    >>> # Create CRUD blueprint using model class directly
    >>> products_bp = CRUDBlueprint(
    ...     'products', __name__,
    ...     model=Product,           # Use class (preferred)
    ...     schema=Product.Schema,   # Auto-generated schema
    ...     url_prefix='/api/products/'
    ... )
    >>> api.register_blueprint(products_bp)

User Authentication Example:
    >>> from flask_more_smorest import User, UserBlueprint
    >>> from sqlalchemy.orm import Mapped, mapped_column
    >>> import sqlalchemy as sa
    >>>
    >>> # Extend User model with custom fields
    >>> class Employee(User):
    ...     employee_id: Mapped[str] = mapped_column(sa.String(50))
    ...     department: Mapped[str] = mapped_column(sa.String(100))
    ...
    ...     def _can_write(self, current_user) -> bool:
    ...         # Custom permission logic
    ...         return self.is_admin or (current_user is not None and self.id == current_user.id)
    >>>
    >>> # Create authentication blueprint
    >>> auth_bp = UserBlueprint(
    ...     model=Employee,
    ...     schema=Employee.Schema
    ... )
    >>> api.register_blueprint(auth_bp)
    >>> # Provides: POST /api/users/login/, GET /api/users/me/, and full CRUD
"""

import logging
import uuid
from typing import TYPE_CHECKING

from .crud.blueprint_operationid import BlueprintOperationIdMixin
from .crud.crud_blueprint import CRUDMethod

# Import utilities
from .crud.query_filtering import generate_filter_schema, get_statements_from_filters

# Import core blueprints
# Import user models and authentication
from .perms import Api, BasePermsModel, UserBlueprint
from .perms import PermsBlueprint as CRUDBlueprint  # Make the Perms version the default
from .perms.jwt import init_jwt

# Import user model mixins
from .perms.model_mixins import (
    ProfileMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UserOwnershipMixin,
)
from .perms.perms_blueprint import PermsBlueprintMixin as BlueprintAccessMixin

# Import migration system
# Import database and models
from .sqla import (
    BaseModel,
    create_migration,
    db,
    downgrade_database,
    init_db,
    init_migrations,
    upgrade_database,
)
from .sqla.base_model import BaseSchema
from .utils import convert_snake_to_camel

# Type stubs for lazy-loaded objects - provides proper typing without premature import
if TYPE_CHECKING:
    from flask_smorest import Blueprint as _Blueprint

    # User models are typed via perms module delegation
    from .perms import (
        AbstractDomain,
        AbstractToken,
        AbstractUser,
        AbstractUserRole,
        AbstractUserSetting,
        get_current_user,
        get_current_user_id,
    )

    # Testing helpers
    from .testing import as_admin, as_user, clear_registration

logger = logging.getLogger(__name__)


__version__ = "0.10.4"
__author__ = "Dave <david@qualisero.com>"
__email__ = "david@qualisero.com"
__description__ = "Enhanced Flask-Smorest blueprints with automatic CRUD operations and extensible user management"

__all__ = [
    "AbstractDomain",
    "AbstractToken",
    "AbstractUser",
    "AbstractUserRole",
    "AbstractUserSetting",
    "Api",
    # Database and models
    "BaseModel",
    "BasePermsModel",
    "BaseSchema",
    "BlueprintAccessMixin",
    "BlueprintOperationIdMixin",
    # Core blueprints
    "CRUDBlueprint",
    "CRUDMethod",
    "ProfileMixin",
    "SoftDeleteMixin",
    # User model mixins
    "TimestampMixin",
    "UserBlueprint",
    "UserOwnershipMixin",
    "__version__",
    "as_admin",
    # Testing helpers
    "as_user",
    "clear_registration",
    "convert_snake_to_camel",
    "create_migration",
    "db",
    "downgrade_database",
    # Utilities
    "generate_filter_schema",
    "get_current_user",
    "get_current_user_id",
    "get_statements_from_filters",
    "init_db",
    # User models and authentication
    "init_jwt",
    # Migration system
    "init_migrations",
    "upgrade_database",
]


def __getattr__(name: str) -> object:
    """Proxy attribute lookups to the perms package for lazy loading."""

    delegated_names = {
        "AbstractUser",
        "AbstractUserRole",
        "AbstractDomain",
        "AbstractToken",
        "AbstractUserSetting",
        "get_current_user",
        "get_current_user_id",
        # Testing helpers
        "as_user",
        "as_admin",
        "clear_registration",
    }

    if name in delegated_names:
        # Testing helpers come from testing module
        if name in {"as_user", "as_admin"}:
            try:
                from . import testing as testing_module

                value = getattr(testing_module, name)
                globals()[name] = value
                return value
            except ImportError as exc:  # pragma: no cover - defensive
                logger.error("Failed to import testing module for %s: %s", name, exc)
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
            except AttributeError as exc:
                logger.error("Attribute %s not found in testing module: %s", name, exc)
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

        # clear_registration is proxied from user_context
        if name == "clear_registration":
            try:
                from .testing import clear_registration as _clear_registration

                globals()[name] = _clear_registration
                return _clear_registration
            except ImportError as exc:  # pragma: no cover - defensive
                logger.error("Failed to import testing module for %s: %s", name, exc)
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
            except AttributeError as exc:
                logger.error("Attribute %s not found in testing module: %s", name, exc)
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

        # Everything else comes from perms module
        try:
            from . import perms as perms_module

            value = getattr(perms_module, name)
            globals()[name] = value
            return value
        except ImportError as exc:  # pragma: no cover - defensive
            logger.error("Failed to import perms module for %s: %s", name, exc)
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
        except AttributeError as exc:
            logger.error("Attribute %s not found in perms module: %s", name, exc)
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
