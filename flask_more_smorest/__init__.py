"""Flask-More-Smorest Extensions.

A powerful extension library for Flask-Smorest that provides automatic CRUD operations,
enhanced blueprints with annotations, advanced query filtering capabilities, and
extensible user management with custom model support.

Example:
    >>> from flask import Flask
    >>> from flask_more_smorest import CRUDBlueprint, BaseModel, db, init_db
    >>>
    >>> app = Flask(__name__)
    >>> app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    >>> init_db(app)
    >>>
    >>> # Create a CRUD blueprint for User model
    >>> user_blueprint = CRUDBlueprint(
    ...     'users', __name__,
    ...     model='User',
    ...     schema='UserSchema'
    ... )
    >>>
    >>> app.register_blueprint(user_blueprint)

Custom User Model Example:
    >>> from flask_more_smorest import User
    >>> from sqlalchemy.orm import Mapped, mapped_column
    >>> import sqlalchemy as sa
    >>> import uuid
    >>>
    >>> class CustomUser(User):
    ...     # Add custom fields
    ...     first_name: Mapped[str] = mapped_column(sa.String(50))
    ...     organization_id: Mapped[uuid.UUID] = mapped_column(
    ...         sa.ForeignKey('organization.id')
    ...     )
    ...
    ...     # Override methods if needed
    ...     def _can_write(self) -> bool:
    ...         # Custom logic: only verified users can write
    ...         return self.email_verified and super()._can_write()
"""

from .blueprint_operationid import BlueprintOperationIdMixin
from .crud.crud_blueprint import CRUDMethod

# Import utilities
from .crud.query_filtering import generate_filter_schema, get_statements_from_filters

# Import core blueprints
from .perms import Api, BasePermsModel, CRUDBlueprint
from .perms.jwt import init_jwt

# Import user model mixins
from .perms.model_mixins import ProfileMixin, SoftDeleteMixin, TimestampMixin, UserCanReadWriteMixin
from .perms.perms_blueprint import PermsBlueprintMixin as BlueprintAccessMixin

# Import user models and authentication
from .perms.user_models import DefaultUserRole, Domain, Token, User, UserRole, UserSetting
from .perms.user_models import current_user as get_current_user
from .perms.user_models import get_current_user_id

# Import migration system
# Import database and models
from .sqla import BaseModel, create_migration, db, downgrade_database, init_db, init_migrations, upgrade_database
from .sqla.base_model import BaseSchema
from .utils import convert_snake_to_camel

__version__ = "0.2.0"
__author__ = "Dave <david@qualisero.com>"
__email__ = "david@qualisero.com"
__description__ = "Enhanced Flask-Smorest blueprints with automatic CRUD operations and extensible user management"

__all__ = [
    "Api",
    # Core blueprints
    "CRUDBlueprint",
    "CRUDMethod",
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
    "UserCanReadWriteMixin",
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
