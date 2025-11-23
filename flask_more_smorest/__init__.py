"""Flask-More-Smorest Extensions.

A powerful extension library for Flask-Smorest that provides automatic CRUD operations,
enhanced blueprints with annotations, advanced query filtering capabilities, and 
extensible user management with custom model support.

Example:
    from flask import Flask
    from flask_more_smorest import CRUDBlueprint, BaseModel
    from flask_more_smorest.database import db
    
    app = Flask(__name__)
    db.init_app(app)
    
    # Create a CRUD blueprint for User model
    user_blueprint = CRUDBlueprint(
        'users', __name__,
        model='User',
        schema='UserSchema'
    )
    
    app.register_blueprint(user_blueprint)

Custom User Model Example:
    from flask_more_smorest import User
    
    class CustomUser(User):
        # Add custom fields
        first_name: Mapped[str] = mapped_column(db.String(50))
        organization_id: Mapped[uuid.UUID] = mapped_column(db.ForeignKey('organization.id'))
        
        # Override methods if needed
        def _can_write(self) -> bool:
            # Custom logic: only verified users can write
            return self.email_verified and super()._can_write()
"""

from typing import TYPE_CHECKING

from .crud_blueprint import CRUDBlueprint
from .enhanced_blueprint import EnhancedBlueprint
from .models import BaseModel, BaseSchema
from .database import db, init_db
from .user import (
    User, UserRole, UserSetting, Domain, Token, DefaultUserRole,
    get_current_user, get_current_user_id,
    TimestampMixin, ProfileMixin, SoftDeleteMixin
)
from .migrations import init_migrations, create_migration, upgrade_database, downgrade_database
from .query_filtering import generate_filter_schema, get_statements_from_filters
from .utils import convert_snake_to_camel

if TYPE_CHECKING:
    pass

__version__ = "0.1.0"
__author__ = "Dave <david@qualisero.com>"
__email__ = "david@qualisero.com"
__description__ = "Enhanced Flask-Smorest blueprints with automatic CRUD operations and extensible user management"

__all__ = [
    # Core blueprints
    "CRUDBlueprint",
    "EnhancedBlueprint",
    
    # Database and models
    "BaseModel",
    "BaseSchema", 
    "db",
    "init_db",
    
    # User models and authentication
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
