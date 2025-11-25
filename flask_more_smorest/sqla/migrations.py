"""Migration utilities for flask-more-smorest.

This module provides utilities for database migrations using Alembic.
It handles the creation of migration environments and provides helpers
for managing database schema changes.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

if TYPE_CHECKING:
    from flask import Flask


def init_migrations(app: "Flask", directory: str = "migrations") -> None:
    """Initialize Alembic migration environment for the application.

    Creates the migrations directory structure and configuration files
    needed for Alembic database migrations.

    Args:
        app: Flask application instance
        directory: Directory name for migration files (default: 'migrations')

    Example:
        >>> from flask import Flask
        >>> from flask_more_smorest.sqla import init_migrations
        >>>
        >>> app = Flask(__name__)
        >>> init_migrations(app)
    """
    migrations_path = Path(directory)

    if not migrations_path.exists():
        # Create alembic environment
        alembic_cfg = _get_alembic_config(app, str(migrations_path))
        command.init(alembic_cfg, str(migrations_path))

        # Update env.py to use our database
        _update_env_py(migrations_path / "env.py")


def create_migration(message: str, directory: str = "migrations") -> None:
    """Create a new migration file.

    Automatically detects changes in the database models and generates
    a migration script.

    Args:
        message: Description of the migration
        directory: Directory containing migration files (default: 'migrations')

    Raises:
        RuntimeError: If migrations directory doesn't exist

    Example:
        >>> create_migration("Add user profile fields")
    """
    from flask import current_app

    migrations_path = Path(directory)
    if not migrations_path.exists():
        raise RuntimeError(f"Migration directory {directory} does not exist. Run init_migrations() first.")

    alembic_cfg = _get_alembic_config(current_app, str(migrations_path))
    command.revision(alembic_cfg, message=message, autogenerate=True)


def upgrade_database(revision: str = "head", directory: str = "migrations") -> None:
    """Upgrade database to specified revision.

    Applies database migrations up to the specified revision.

    Args:
        revision: Target revision (default: 'head' for latest)
        directory: Directory containing migration files (default: 'migrations')

    Example:
        >>> upgrade_database()  # Upgrade to latest
        >>> upgrade_database("ae1027a6acf")  # Upgrade to specific revision
    """
    from flask import current_app

    migrations_path = Path(directory)
    alembic_cfg = _get_alembic_config(current_app, str(migrations_path))
    command.upgrade(alembic_cfg, revision)


def downgrade_database(revision: str, directory: str = "migrations") -> None:
    """Downgrade database to specified revision.

    Reverts database migrations to the specified revision.

    Args:
        revision: Target revision to downgrade to
        directory: Directory containing migration files (default: 'migrations')

    Example:
        >>> downgrade_database("-1")  # Downgrade one revision
        >>> downgrade_database("ae1027a6acf")  # Downgrade to specific revision
    """
    from flask import current_app

    migrations_path = Path(directory)
    alembic_cfg = _get_alembic_config(current_app, str(migrations_path))
    command.downgrade(alembic_cfg, revision)


def get_migration_history(directory: str = "migrations") -> list[str]:
    """Get list of migration revisions.

    Args:
        directory: Directory containing migration files (default: 'migrations')

    Returns:
        List of revision IDs in the migration history
    """
    from flask import current_app

    migrations_path = Path(directory)
    alembic_cfg = _get_alembic_config(current_app, str(migrations_path))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    return [rev.revision for rev in script_dir.walk_revisions()]


def _get_alembic_config(app: "Flask", migrations_dir: str) -> Config:
    """Get Alembic configuration for the application.

    Args:
        app: Flask application instance
        migrations_dir: Path to migrations directory

    Returns:
        Configured Alembic Config instance
    """
    alembic_cfg = Config()

    # Set the script location
    alembic_cfg.set_main_option("script_location", migrations_dir)

    # Set the database URL
    with app.app_context():
        database_url = app.config.get("SQLALCHEMY_DATABASE_URI")
        if database_url:
            alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    return alembic_cfg


def _update_env_py(env_path: Path) -> None:
    """Update the generated env.py to work with our application.

    Args:
        env_path: Path to the env.py file to update
    """

    env_content = '''"""Alembic environment for flask-more-smorest."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your application and models here
from flask import current_app
from flask_more_smorest.sqla import db

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                print("No changes detected.")

    connectable = current_app.extensions['sqlalchemy'].engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

    env_path.write_text(env_content)
