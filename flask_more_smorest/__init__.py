"""Flask-More-Smorest Extensions.

A powerful extension library for Flask-Smorest that provides automatic CRUD operations,
enhanced blueprints with annotations, and advanced query filtering capabilities.

Example:
    from flask import Flask
    from flask_more_smorest import CRUDBlueprint

    app = Flask(__name__)

    # Create a CRUD blueprint for User model
    user_blueprint = CRUDBlueprint(
        'users', __name__,
        model='User',
        schema='UserSchema'
    )

    app.register_blueprint(user_blueprint)
"""

from typing import TYPE_CHECKING

from .crud_blueprint import CRUDBlueprint
from .enhanced_blueprint import EnhancedBlueprint
from .query_filtering import generate_filter_schema, get_statements_from_filters
from .utils import convert_snake_to_camel

if TYPE_CHECKING:
    pass

__version__ = "0.1.0"
__author__ = "Dave <david@qualisero.com>"
__email__ = "david@qualisero.com"
__description__ = "Enhanced Flask-Smorest blueprints with automatic CRUD operations"

__all__ = [
    "CRUDBlueprint",
    "EnhancedBlueprint",
    "generate_filter_schema",
    "get_statements_from_filters",
    "convert_snake_to_camel",
    "__version__",
]
