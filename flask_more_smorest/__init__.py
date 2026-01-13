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
    ...     def _can_write(self) -> bool:
    ...         # Custom permission logic
    ...         return self.is_admin or self.id == get_current_user_id()
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
        DefaultUserRole,
        Domain,
        Token,
        User,
        UserRole,
        UserSetting,
        get_current_user,
        get_current_user_id,
        user_bp,
    )

logger = logging.getLogger(__name__)


__version__ = "0.7.1"
__author__ = "Dave <david@qualisero.com>"
__email__ = "david@qualisero.com"
__description__ = "Enhanced Flask-Smorest blueprints with automatic CRUD operations and extensible user management"

__all__ = [
    "Api",
    # Core blueprints
    "CRUDBlueprint",
    "CRUDMethod",
    "UserBlueprint",
    "user_bp",
    "BlueprintAccessMixin",
    "BlueprintOperationIdMixin",
    # Database and models
    "BaseModel",
    "BasePermsModel",
    "BaseSchema",
    "db",
    "init_db",
    # User models and authentication
    "init_jwt",
    "User",
    "UserRole",
    "UserSetting",
    "Domain",
    "Token",
    "DefaultUserRole",
    "get_current_user",
    "get_current_user_id",
    # User model mixins
    "TimestampMixin",
    "ProfileMixin",
    "SoftDeleteMixin",
    "UserOwnershipMixin",
    # Migration system
    "init_migrations",
    "create_migration",
    "upgrade_database",
    "downgrade_database",
    # Utilities
    "generate_filter_schema",
    "get_statements_from_filters",
    "convert_snake_to_camel",
    "__version__",
]


def __getattr__(name: str) -> object:
    """Proxy attribute lookups to the perms package for lazy loading."""

    delegated_names = {
        "User",
        "UserRole",
        "UserSetting",
        "Domain",
        "Token",
        "DefaultUserRole",
        "get_current_user",
        "get_current_user_id",
        "user_bp",
    }

    if name in delegated_names:
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
