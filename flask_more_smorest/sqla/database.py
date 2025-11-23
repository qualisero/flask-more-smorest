"""Database configuration and utilities for flask-more-smorest.

This module provides the core SQLAlchemy setup and utilities for
configuring custom User models and other database-related functionality.
"""

from typing import TYPE_CHECKING
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    from flask import Flask


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    This serves as the declarative base for all models in the application.
    It provides the foundation for SQLAlchemy's ORM functionality.
    """

    pass


# Main database instance
db = SQLAlchemy(model_class=Base)


def init_db(app: "Flask") -> None:
    """Initialize the database with the Flask application.

    This function binds the SQLAlchemy database instance to the Flask
    application, making it available throughout the application context.

    Args:
        app: Flask application instance to initialize the database with

    Example:
        >>> from flask import Flask
        >>> from flask_more_smorest.sqla import init_db
        >>>
        >>> app = Flask(__name__)
        >>> app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
        >>> init_db(app)
    """
    db.init_app(app)
