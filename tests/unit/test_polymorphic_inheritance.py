"""Test polymorphic inheritance for Token and UserSetting models."""

from flask_more_smorest.perms.models import Token, User, UserSetting
from flask_more_smorest.sqla import db as sqla_db


def test_token_polymorphic_subclass(unit_app, db_session):
    """Test that Token supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create Token instances
    token1 = Token(user_id=user.id, token="token_123", description="Token 1")
    token2 = Token(user_id=user.id, token="token_456", description="Token 2")
    sqla_db.session.add_all([token1, token2])
    sqla_db.session.commit()

    # Verify discriminator is set correctly
    assert token1.discriminator == "token"
    assert token2.discriminator == "token"

    # Verify tokens can be queried
    all_tokens = sqla_db.session.query(Token).all()
    assert len(all_tokens) == 2

    # Verify relationship works
    assert len(user.tokens) == 2


def test_user_setting_polymorphic_subclass(unit_app, db_session):
    """Test that UserSetting supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create UserSetting instances
    setting1 = UserSetting(user_id=user.id, key="theme", value="dark")
    setting2 = UserSetting(user_id=user.id, key="language", value="en")
    sqla_db.session.add_all([setting1, setting2])
    sqla_db.session.commit()

    # Verify discriminator is set correctly
    assert setting1.discriminator == "user_setting"
    assert setting2.discriminator == "user_setting"

    # Verify settings can be queried
    all_settings = sqla_db.session.query(UserSetting).all()
    assert len(all_settings) == 2

    # Verify relationship works
    assert len(user.settings) == 2


def test_token_default_discriminator(unit_app, db_session):
    """Test that Token has correct default discriminator."""
    sqla_db.create_all()

    user = User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    token = Token(user_id=user.id, token="token_123")
    sqla_db.session.add(token)
    sqla_db.session.commit()

    assert token.discriminator == "token"


def test_user_setting_default_discriminator(unit_app, db_session):
    """Test that UserSetting has correct default discriminator."""
    sqla_db.create_all()

    user = User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    setting = UserSetting(user_id=user.id, key="test_key", value="test_value")
    sqla_db.session.add(setting)
    sqla_db.session.commit()

    assert setting.discriminator == "user_setting"
