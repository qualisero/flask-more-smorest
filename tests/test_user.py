"""Tests for User model and authentication functionality."""

import pytest
from unittest.mock import patch

from flask_more_smorest.user import (
    User,
    UserRole,
    UserSetting,
    get_current_user,
    get_current_user_id,
    DefaultUserRole,
)
from flask_more_smorest.database import db


class TestUserModel:
    """Tests for User model functionality."""

    def test_user_creation_with_password(self, app):
        """Test creating user with password hashing."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com", password="secret123")
            user.save()

            # Password should be hashed
            assert user.password is not None
            assert isinstance(user.password, bytes)
            assert user.is_password_correct("secret123")
            assert not user.is_password_correct("wrong")

    def test_user_admin_properties(self, app):
        """Test admin and superadmin properties."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")
            user.save()

            # Initially not admin
            assert not user.is_admin
            assert not user.is_superadmin

    def test_user_has_role(self, app):
        """Test has_role method."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")
            user.save()

            # Initially has no roles
            role_enum = DefaultUserRole
            assert not user.has_role(role_enum.USER)
            assert not user.has_role(role_enum.ADMIN)


class TestUserRole:
    """Tests for UserRole model."""

    def test_user_role_creation(self, app):
        """Test creating user roles."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")
            user.save()

            role_enum: DefaultUserRole = DefaultUserRole
            role = UserRole(user=user, role=role_enum.ADMIN)
            role.save()

            assert role.user_id == user.id
            assert role.role == role_enum.ADMIN
            assert role.user == user

    def test_user_role_enum_values(self):
        """Test UserRole enum values."""
        role_enum = DefaultUserRole
        assert role_enum.SUPERADMIN == "superadmin"
        assert role_enum.ADMIN == "admin"
        assert role_enum.ADMIN == "admin"
        assert role_enum.USER == "user"


class TestUserSetting:
    """Tests for UserSetting model."""

    def test_user_setting_creation(self, app):
        """Test creating user settings."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")
            user.save()

            setting = UserSetting(user=user, key="theme", value="dark")
            setting.save()

            assert setting.user_id == user.id
            assert setting.key == "theme"
            assert setting.value == "dark"
            assert setting.user == user


class TestUserHelperFunctions:
    """Tests for user helper functions."""

    def test_get_current_user(self):
        """Test get_current_user function."""
        # This is just a wrapper around flask_jwt_extended.current_user
        from flask_more_smorest.user import current_user

        result = get_current_user()
        assert result == current_user

    def test_get_current_user_id_without_jwt(self):
        """Test get_current_user_id without valid JWT."""
        with patch("flask_more_smorest.user.verify_jwt_in_request") as mock_verify:
            from flask_jwt_extended.exceptions import JWTDecodeError

            mock_verify.side_effect = JWTDecodeError("Invalid token")

            result = get_current_user_id()
            assert result is None

    def test_get_current_user_id_with_exception(self):
        """Test get_current_user_id with other exceptions."""
        with patch("flask_more_smorest.user.verify_jwt_in_request") as mock_verify:
            mock_verify.side_effect = Exception("Some error")

            result = get_current_user_id()
            assert result is None


class TestUserModelBasics:
    """Tests for basic User model functionality."""

    def test_user_password_methods(self, app):
        """Test password setting and checking."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")
            user.set_password("secret123")

            assert user.password is not None
            assert user.is_password_correct("secret123")
            assert not user.is_password_correct("wrong")

    def test_user_model_fields(self, app):
        """Test that User model has expected fields."""
        with app.app_context():
            db.create_all()  # Create tables first

            user = User(email="test@example.com")

            # Should have basic fields
            assert hasattr(user, "id")
            assert hasattr(user, "email")
            assert hasattr(user, "password")
            assert hasattr(user, "is_enabled")
            assert hasattr(user, "created_at")
            assert hasattr(user, "updated_at")
            assert hasattr(user, "roles")
            assert hasattr(user, "settings")
