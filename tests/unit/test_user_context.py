"""Unit tests for flask-more-smorest.perms.user_context module."""

from __future__ import annotations

import pytest

from flask_more_smorest import db
from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models.defaults import (
    BaseRoleEnum,
    DefaultUser,
    DefaultUserRole,
)
from flask_more_smorest.perms.user_context import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    get_current_user_id,
    is_current_user_admin,
    is_current_user_superadmin,
)


@pytest.mark.usefixtures("reset_user_context")
class TestUserContext:
    def test_init_fms_registers_getter(self, app, db_session) -> None:
        user = DefaultUser(email="test@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        def my_get_user() -> DefaultUser | None:
            return user

        init_fms(get_current_user=my_get_user)

        current = DefaultUser.get_current_user()
        assert current is user

    def test_clear_registration_resets_getter(self, app, db_session) -> None:
        user = DefaultUser(email="clear@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)
        clear_registration()

        assert DefaultUser.get_current_user() is None

    def test_user_type_filter_returns_none(self, app, db_session) -> None:
        class OtherUser(DefaultUser):
            __mapper_args__ = {"polymorphic_identity": "other_user"}

        user = DefaultUser(email="other@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert OtherUser.get_current_user() is None

    def test_get_current_user_id(self, app, db_session) -> None:
        user = DefaultUser(email="id@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert get_current_user_id() == user.id

    def test_is_current_user_admin(self, app, db_session) -> None:
        user = DefaultUser(email="admin@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        role = DefaultUserRole(user_id=user.id, role=BaseRoleEnum.ADMIN, domain_id=None)
        user.roles.append(role)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert is_current_user_admin() is True
        assert user.has_role(ROLE_ADMIN) is True
        assert user.has_role(ROLE_SUPERADMIN) is False

    def test_is_current_user_superadmin(self, app, db_session) -> None:
        user = DefaultUser(email="super@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        role = DefaultUserRole(user_id=user.id, role=BaseRoleEnum.SUPERADMIN, domain_id=None)
        user.roles.append(role)
        db.session.commit()

        init_fms(get_current_user=lambda: user)

        assert is_current_user_superadmin() is True
        assert user.has_role(ROLE_SUPERADMIN) is True
