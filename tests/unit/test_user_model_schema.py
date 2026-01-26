"""Tests for User model database schema and foreign key relationships.

This module tests that foreign key relationships are properly created between
User-related tables (UserRole, Token, Domain, UserSetting).
"""

import pytest
from sqlalchemy import inspect

from flask_more_smorest import Api
from flask_more_smorest.sqla import db


@pytest.fixture
def api(unit_api: Api) -> Api:
    """Return API fixture for type compatibility."""
    return unit_api


@pytest.mark.usefixtures("unit_app", "api", "db_session")
class TestUserModelSchema:
    """Tests for User model database schema."""

    def test_foreign_key_relationships(self, unit_app, api, db_session) -> None:
        """Test that foreign key relationships are properly created between User-related tables."""
        inspector = inspect(db.engine)

        # Check user_role foreign keys to User and Domain
        user_role_fks = inspector.get_foreign_keys("user_role")
        fk_columns = {fk["constrained_columns"][0] for fk in user_role_fks}
        assert "user_id" in fk_columns, "user_role should have FK to user"
        assert "domain_id" in fk_columns, "user_role should have FK to domain"

        # Check token foreign key to User
        token_fks = inspector.get_foreign_keys("token")
        token_fk_columns = {fk["constrained_columns"][0] for fk in token_fks}
        assert "user_id" in token_fk_columns, "token should have FK to user"

        # Check user_setting foreign key to User
        setting_fks = inspector.get_foreign_keys("user_setting")
        setting_fk_columns = {fk["constrained_columns"][0] for fk in setting_fks}
        assert "user_id" in setting_fk_columns, "user_setting should have FK to user"
