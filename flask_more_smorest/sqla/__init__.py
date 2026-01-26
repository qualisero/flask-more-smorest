"""SQLAlchemy integration module.

This module provides the core SQLAlchemy integration for flask-more-smorest,
including the database instance, base model, schema utilities, and migration tools.
"""

from .base_model import BaseModel
from .database import db, get_request_query_stats, init_db
from .migrations import (
    create_migration,
    downgrade_database,
    init_migrations,
    upgrade_database,
)
from .schema import BaseSchema, create_model_schema

__all__ = [
    "BaseModel",
    "BaseSchema",
    "create_migration",
    "create_model_schema",
    "db",
    "downgrade_database",
    "get_request_query_stats",
    "init_db",
    "init_migrations",
    "upgrade_database",
]
