"""Test polymorphic inheritance for DefaultToken and DefaultUserSetting models."""

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.perms.models.defaults import (
    DefaultDomain,
    DefaultToken,
    DefaultUser,
    DefaultUserRole,
    DefaultUserSetting,
)
from flask_more_smorest.sqla import db as sqla_db


def test_token_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that DefaultToken supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create DefaultToken instances
    token1 = DefaultToken(user_id=user.id, token="token_123", description="DefaultToken 1")
    token2 = DefaultToken(user_id=user.id, token="token_456", description="DefaultToken 2")
    sqla_db.session.add_all([token1, token2])
    sqla_db.session.commit()

    # Verify discriminator is set correctly
    assert token1.discriminator == "token"
    assert token2.discriminator == "token"

    # Verify tokens can be queried
    all_tokens = sqla_db.session.query(DefaultToken).all()
    assert len(all_tokens) == 2

    # Verify relationship works
    assert len(user.tokens) == 2


def test_user_setting_polymorphic_subclass(unit_app, db_session):
    """Test that DefaultUserSetting supports polymorphic inheritance via discriminator."""

    sqla_db.create_all()

    # Create a user
    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Create DefaultUserSetting instances
    setting1 = DefaultUserSetting(user_id=user.id, key="theme", value="dark")
    setting2 = DefaultUserSetting(user_id=user.id, key="language", value="en")
    sqla_db.session.add_all([setting1, setting2])
    sqla_db.session.commit()

    # Verify discriminator is set correctly
    assert setting1.discriminator == "user_setting"
    assert setting2.discriminator == "user_setting"

    # Verify settings can be queried
    all_settings = sqla_db.session.query(DefaultUserSetting).all()
    assert len(all_settings) == 2

    # Verify relationship works
    assert len(user.settings) == 2


def test_token_default_discriminator(unit_app, db_session):
    """Test that DefaultToken has correct default discriminator."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    token = DefaultToken(user_id=user.id, token="token_123")
    sqla_db.session.add(token)
    sqla_db.session.commit()

    assert token.discriminator == "token"


def test_user_setting_default_discriminator(unit_app, db_session):
    """Test that DefaultUserSetting has correct default discriminator."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    setting = DefaultUserSetting(user_id=user.id, key="test_key", value="test_value")
    sqla_db.session.add(setting)
    sqla_db.session.commit()

    assert setting.discriminator == "user_setting"


def test_domain_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that DefaultDomain supports polymorphic inheritance via discriminator."""

    class CustomDefaultDomain(DefaultDomain):
        __mapper_args__ = {"polymorphic_identity": "custom_domain"}

    sqla_db.create_all()

    domain = CustomDefaultDomain(name="test", display_name="Test", active=True)
    sqla_db.session.add(domain)
    sqla_db.session.commit()

    assert domain.discriminator == "custom_domain"
    assert sqla_db.session.query(DefaultDomain).count() == 1


def test_user_polymorphic_subclass(unit_app: Any, db_session: Any) -> None:
    """Test that custom AbstractUser supports polymorphic inheritance via discriminator."""

    class CustomUser(AbstractUser):
        __mapper_args__ = {"polymorphic_identity": "custom_user"}

        id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
        email: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)
        password: Mapped[bytes | None] = mapped_column(sa.LargeBinary(128), nullable=True)
        is_enabled: Mapped[bool] = mapped_column(sa.Boolean(), default=True)
        discriminator: Mapped[str] = mapped_column(
            sa.String(50),
            default="custom_user",
            nullable=False,
            server_default="custom_user",
        )

    clear_registration()
    init_fms(
        user=CustomUser,
        role=DefaultUserRole,
        token=DefaultToken,
        domain=DefaultDomain,
        setting=DefaultUserSetting,
    )

    sqla_db.drop_all()
    sqla_db.create_all()

    user = CustomUser(email="custom@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.commit()

    assert user.discriminator == "custom_user"
    assert sqla_db.session.query(CustomUser).count() == 1

    clear_registration()
    init_fms(
        user=DefaultUser,
        role=DefaultUserRole,
        token=DefaultToken,
        domain=DefaultDomain,
        setting=DefaultUserSetting,
    )
