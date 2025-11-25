"""SQLAlchemy integration module.

This module provides the core SQLAlchemy integration for flask-more-smorest,
including the database instance, base model, and migration utilities.
"""

from .base_model import BaseModel
from .database import db, init_db
from .migrations import create_migration, downgrade_database, init_migrations, upgrade_database

__all__ = [
    "BaseModel",
    "db",
    "init_db",
    "init_migrations",
    "create_migration",
    "upgrade_database",
    "downgrade_database",
]
