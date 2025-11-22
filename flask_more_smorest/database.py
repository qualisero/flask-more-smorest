"""Database configuration and utilities for flask-more-smorest.

This module provides the core SQLAlchemy setup and utilities for
configuring custom User models and other database-related functionality.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

# Main database instance
db = SQLAlchemy(model_class=Base)


def init_db(app):
    """Initialize the database with the Flask application.
    
    Args:
        app: Flask application instance
        
    Example:
        from flask import Flask
        from flask_more_smorest.database import init_db
        
        app = Flask(__name__)
        init_db(app)
    """
    db.init_app(app)
