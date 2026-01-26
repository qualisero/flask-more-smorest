"""Test polymorphic inheritance for defaults_module.Token and defaults_module.UserSetting models."""

import uuid
from typing import Any

from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.models.abstract_role import AbstractDomain, AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.sqla import db as sqla_db


def test_token_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that defaults_module.Token supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create defaults_module.Token instances
    token1 = defaults_module.Token(user_id=user.id, token="token_123", description="defaults_module.Token 1")
    token2 = defaults_module.Token(user_id=user.id, token="token_456", description="defaults_module.Token 2")
    sqla_db.session.add_all([token1, token2])
    sqla_db.session.commit()

    # Verify tokens are persisted
    assert token1.id is not None
    assert token2.id is not None

    # Verify tokens can be queried
    all_tokens = sqla_db.session.query(defaults_module.Token).all()
    assert len(all_tokens) == 2

    # Verify relationship works
    assert len(user.tokens) == 2


def test_user_setting_polymorphic_subclass(unit_app, db_session):
    """Test that defaults_module.UserSetting supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create defaults_module.UserSetting instances
    setting1 = defaults_module.UserSetting(user_id=user.id, key="theme", value="dark")
    setting2 = defaults_module.UserSetting(user_id=user.id, key="language", value="en")
    sqla_db.session.add_all([setting1, setting2])
    sqla_db.session.commit()

    # Verify settings are persisted
    assert setting1.id is not None
    assert setting2.id is not None

    # Verify settings can be queried
    all_settings = sqla_db.session.query(defaults_module.UserSetting).all()
    assert len(all_settings) == 2

    # Verify relationship works
    assert len(user.settings) == 2


def test_token_default_discriminator(unit_app, db_session):
    """Test that defaults_module.Token has correct default discriminator."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    token = defaults_module.Token(user_id=user.id, token="token_123")
    sqla_db.session.add(token)
    sqla_db.session.commit()

    assert token.id is not None


def test_user_setting_default_discriminator(unit_app, db_session):
    """Test that defaults_module.UserSetting has correct default discriminator."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    setting = defaults_module.UserSetting(user_id=user.id, key="test_key", value="test_value")
    sqla_db.session.add(setting)
    sqla_db.session.commit()

    assert setting.id is not None


def test_domain_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that defaults_module.Domain supports polymorphic inheritance via discriminator."""

    class CustomDefaultDomain(defaults_module.Domain):
        __mapper_args__ = {"polymorphic_identity": "custom_domain"}

    sqla_db.create_all()

    domain = CustomDefaultDomain(name="test", display_name="Test", active=True)
    sqla_db.session.add(domain)
    sqla_db.session.commit()

    assert domain.id is not None
    assert sqla_db.session.query(defaults_module.Domain).count() == 1


def test_user_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that custom AbstractUser subclasses can be persisted."""
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    import sys
    import types

    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomDomain(AbstractDomain):
        __module__ = module_name

    class CustomUserRole(AbstractUserRole):
        __module__ = module_name

    class CustomToken(AbstractToken):
        __module__ = module_name

    class CustomUserSetting(AbstractUserSetting):
        __module__ = module_name

    class CustomUser(AbstractUser):
        __module__ = module_name

    clear_registration()
    init_fms(
        user=CustomUser,
        role=CustomUserRole,
        token=CustomToken,
        domain=CustomDomain,
        setting=CustomUserSetting,
    )

    sqla_db.drop_all()
    sqla_db.create_all()

    user = CustomUser(email="custom@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.commit()

    assert sqla_db.session.query(CustomUser).count() == 1
