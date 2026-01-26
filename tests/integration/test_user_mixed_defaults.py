"""Integration test: custom user model + default related models."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import Api, db, init_db, init_jwt
from flask_more_smorest.perms import UserBlueprint, clear_registration, init_fms
from flask_more_smorest.perms.models.abstract_role import AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser

# Type aliases for dynamically created classes
CustomUser: Any
CustomUserRole: Any
CustomToken: Any
CustomUserSetting: Any
CustomDomain: Any


@pytest.fixture(scope="module", autouse=True)
def custom_models() -> Iterator[SimpleNamespace]:
    import sys
    import types

    from flask_more_smorest.perms.models.abstract_role import AbstractDomain

    clear_registration()
    db.metadata.clear()
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomDomain(AbstractDomain):
        __module__ = module_name

    class CustomUser(AbstractUser):
        __module__ = module_name
        # Only add custom fields, everything else inherited from AbstractUser
        nickname: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)

    class CustomUserRole(AbstractUserRole):
        __module__ = module_name

    class CustomToken(AbstractToken):
        __module__ = module_name
        # Add custom fields for token
        description: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
        expires_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)
        revoked: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
        revoked_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(), nullable=True)

    class CustomUserSetting(AbstractUserSetting):
        __module__ = module_name
        # Add custom field for setting
        scope: Mapped[str] = mapped_column(sa.String(50), default="user", nullable=False)

    models = SimpleNamespace(
        CustomDomain=CustomDomain,
        CustomUser=CustomUser,
        CustomUserRole=CustomUserRole,
        CustomToken=CustomToken,
        CustomUserSetting=CustomUserSetting,
    )

    try:
        yield models
    finally:
        sys.modules.pop(module_name, None)
        clear_registration()


@pytest.fixture
def app(custom_models: SimpleNamespace) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Mixed API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "jwt-secret"

    init_fms(
        user=custom_models.CustomUser,
        role=custom_models.CustomUserRole,
        token=custom_models.CustomToken,
        domain=custom_models.CustomDomain,
        setting=custom_models.CustomUserSetting,
    )
    init_db(app)
    init_jwt(app)

    return app


def test_mixed_defaults(app: Flask) -> None:
    api = Api(app)
    user_bp = UserBlueprint(register=False)
    api.register_blueprint(user_bp)

    # Get classes from the custom_models fixture
    from flask_more_smorest.perms import user_registry

    CustomUser = user_registry.get_user_model()
    CustomUserRole = user_registry.get_role_model()
    CustomToken = user_registry.get_token_model()
    CustomUserSetting = user_registry.get_setting_model()
    DefaultDomain = user_registry.get_domain_model()

    with app.app_context():
        db.create_all()
        user = CustomUser(email="sam@example.com", nickname="Sam")
        user.set_password("secret")
        db.session.add(user)
        db.session.commit()

        domain = DefaultDomain(name="main", display_name="Main", active=True)
        db.session.add(domain)
        db.session.flush()

        role = CustomUserRole(user_id=user.id, domain_id=domain.id, role="ADMIN")
        token = CustomToken(user_id=user.id, token=str(uuid.uuid4()))
        setting = CustomUserSetting(user_id=user.id, key="theme", value="light")

        db.session.add_all([role, token, setting])
        db.session.commit()

        db.session.refresh(user)
        assert len(user.roles) == 1
        assert len(user.tokens) == 1
        assert len(user.settings) == 1

    client = app.test_client()
    resp = client.post("/api/users/login/", json={"email": "sam@example.com", "password": "secret"})
    assert resp.status_code == 200
