"""Tests for User model database schema and table structure.

This module tests that the User model and related tables (UserRole, Token, Domain, UserSetting)
are created with the correct columns, foreign keys, and relationships.
"""

import pytest
from sqlalchemy import inspect

from flask_more_smorest import Api
from flask_more_smorest.sqla import db


@pytest.fixture
def api(unit_api: Api) -> Api:
    """Return the API fixture for type compatibility."""
    return unit_api


@pytest.mark.usefixtures("unit_app", "api", "db_session")
class TestUserModelSchema:
    """Tests for User model database schema."""

    def test_user_related_tables_created(self, unit_app, api, db_session) -> None:
        """Test that all User-related tables are created."""

        # Get inspector
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())

        # Core user tables that should exist
        expected_tables = {
            "user",  # Main User table
            "domain",  # Domain table for multi-tenancy
            "user_role",  # UserRole table
            "token",  # Token table for API tokens
            "user_setting",  # UserSetting table
        }

        for table in expected_tables:
            assert table in table_names, f"Table '{table}' should be created"

    def test_user_table_columns(self, unit_app, api, db_session) -> None:
        """Test that user table has all expected columns."""

        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("user")}

        expected_columns = {
            "id",  # From BaseModel
            "created_at",  # From BaseModel
            "updated_at",  # From BaseModel
            "email",  # From User
            "password",  # From User
            "is_enabled",  # From User
        }

        for col in expected_columns:
            assert col in columns, f"Column '{col}' should exist in user table"

    def test_user_role_table_columns(self, unit_app, api, db_session) -> None:
        """Test that user_role table has all expected columns."""

        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("user_role")}

        expected_columns = {
            "id",  # From BaseModel
            "created_at",  # From BaseModel
            "updated_at",  # From BaseModel
            "user_id",  # Foreign key to User
            "domain_id",  # Foreign key to Domain
            "role",  # Role string value
        }

        for col in expected_columns:
            assert col in columns, f"Column '{col}' should exist in user_role table"

    def test_token_table_columns(self, unit_app, api, db_session) -> None:
        """Test that token table has all expected columns."""

        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("token")}

        expected_columns = {
            "id",  # From BaseModel
            "created_at",  # From BaseModel
            "updated_at",  # From BaseModel
            "user_id",  # From UserOwnershipMixin
            "token",  # Token string
            "description",  # Token description
            "expires_at",  # Expiration datetime
            "revoked",  # Revoked flag
            "revoked_at",  # Revoked datetime
        }

        for col in expected_columns:
            assert col in columns, f"Column '{col}' should exist in token table"

    def test_domain_table_columns(self, unit_app, api, db_session) -> None:
        """Test that domain table has all expected columns."""

        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("domain")}

        expected_columns = {
            "id",  # From BaseModel
            "created_at",  # From BaseModel
            "updated_at",  # From BaseModel
            "name",  # Domain name
            "display_name",  # Display name
            "active",  # Active flag
        }

        for col in expected_columns:
            assert col in columns, f"Column '{col}' should exist in domain table"

    def test_user_setting_table_columns(self, unit_app, api, db_session) -> None:
        """Test that user_setting table has all expected columns."""

        inspector = inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("user_setting")}

        expected_columns = {
            "id",  # From BaseModel
            "created_at",  # From BaseModel
            "updated_at",  # From BaseModel
            "user_id",  # From UserOwnershipMixin
            "key",  # Setting key
            "value",  # Setting value
        }

        for col in expected_columns:
            assert col in columns, f"Column '{col}' should exist in user_setting table"

    def test_all_created_tables_summary(self, unit_app, api, db_session) -> None:
        """Test that all core User-related tables are created."""

        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())

        # Core user-related tables that must exist
        core_tables = {
            "domain",  # Multi-tenancy domain support
            "token",  # API tokens for user authentication
            "user",  # Main user model
            "user_role",  # User roles with domain scoping
            "user_setting",  # User key-value settings storage
        }

        # Verify all core tables are present (other tests may add more tables)
        for table in core_tables:
            assert table in table_names, f"Core table '{table}' should be created"

        # Verify user table has expected columns
        user_columns = {col["name"] for col in inspector.get_columns("user")}
        expected_user_columns = {"id", "email", "password", "is_enabled", "created_at", "updated_at"}
        assert (
            expected_user_columns <= user_columns
        ), f"User table should have columns: {expected_user_columns}. Found: {user_columns}"

    def test_foreign_key_relationships(self, unit_app, api, db_session) -> None:
        """Test that foreign key relationships are properly created."""

        inspector = inspect(db.engine)

        # Check user_role foreign keys
        user_role_fks = inspector.get_foreign_keys("user_role")
        fk_columns = {fk["constrained_columns"][0] for fk in user_role_fks}
        assert "user_id" in fk_columns, "user_role should have FK to user"
        assert "domain_id" in fk_columns, "user_role should have FK to domain"

        # Check token foreign keys
        token_fks = inspector.get_foreign_keys("token")
        token_fk_columns = {fk["constrained_columns"][0] for fk in token_fks}
        assert "user_id" in token_fk_columns, "token should have FK to user"

        # Check user_setting foreign keys
        setting_fks = inspector.get_foreign_keys("user_setting")
        setting_fk_columns = {fk["constrained_columns"][0] for fk in setting_fks}
        assert "user_id" in setting_fk_columns, "user_setting should have FK to user"
