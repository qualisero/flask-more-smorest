"""Unit tests for flask-more-smorest.perms.user_context module."""

from __future__ import annotations

import pytest
from flask import Flask

from flask_more_smorest import db
from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.user_context import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    get_current_user_id,
    is_current_user_admin,
    is_current_user_superadmin,
)


class TestUserContext:
    @pytest.fixture(autouse=True)
    def _register_default_models(self, reset_user_context: None, app: Flask) -> None:
        """Re-register the default perms models cleared by ``reset_user_context``.

        The SQLAlchemy mapper for ``User`` cannot configure without a registered
        ``UserRole`` model, so every test in this class must register the defaults
        before instantiating ``User``. Each test still registers its own
        ``get_current_user`` getter, which is what these tests actually assert on.
        """
        init_fms(
            user=defaults_module.User,
            role=defaults_module.UserRole,
            token=defaults_module.Token,
            domain=defaults_module.Domain,
            setting=defaults_module.UserSetting,
        )

    def test_init_fms_registers_getter(self, app: Flask, db_session: None) -> None:
        user = defaults_module.User(email="test@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        def my_get_user() -> defaults_module.User | None:
            return user

        init_fms(get_current_user=my_get_user)

        current = defaults_module.User.get_current_user()
        assert current is user

    def test_clear_registration_resets_getter(self, app: Flask, db_session: None) -> None:
        user = defaults_module.User(email="clear@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)
        clear_registration()

        assert defaults_module.User.get_current_user() is None

    def test_user_type_filter_returns_none(self, app: Flask, db_session: None) -> None:
        class OtherUser(defaults_module.User):
            __abstract__ = True

        user = defaults_module.User(email="other@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert OtherUser.get_current_user() is None

    def test_get_current_user_id(self, app: Flask, db_session: None) -> None:
        user = defaults_module.User(email="id@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert get_current_user_id() == user.id

    def test_is_current_user_admin(self, app: Flask, db_session: None) -> None:
        user = defaults_module.User(email="admin@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        role = defaults_module.UserRole(user_id=user.id, role=defaults_module.BaseRoleEnum.ADMIN, domain_id=None)
        user.roles.append(role)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert is_current_user_admin() is True
        assert user.has_role(ROLE_ADMIN) is True
        assert user.has_role(ROLE_SUPERADMIN) is False

    def test_is_current_user_superadmin(self, app: Flask, db_session: None) -> None:
        user = defaults_module.User(email="super@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        role = defaults_module.UserRole(user_id=user.id, role=defaults_module.BaseRoleEnum.SUPERADMIN, domain_id=None)
        user.roles.append(role)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert is_current_user_superadmin() is True
        assert user.has_role(ROLE_SUPERADMIN) is True
