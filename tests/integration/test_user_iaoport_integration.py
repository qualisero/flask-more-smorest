"""Integration test: iaoport-style FMS integration (custom models + blueprint)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token
from marshmallow import Schema, fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import Api, CRUDBlueprint, CRUDMethod, db, init_db, init_jwt
from flask_more_smorest.error import UnauthorizedError
from flask_more_smorest.error.error_handlers import RequestHandlers
from flask_more_smorest.perms import UserBlueprint, clear_registration, init_fms
from flask_more_smorest.perms.model_mixins import ProfileMixin
from flask_more_smorest.perms.models.abstract_role import AbstractDomain, AbstractUserRole
from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
from flask_more_smorest.perms.models.abstract_token import AbstractToken
from flask_more_smorest.perms.models.abstract_user import AbstractUser


class LoginArgsSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)
    domain = fields.String(required=False)


class TokenLoginArgsSchema(Schema):
    token = fields.String(required=True)
    domain = fields.String(required=False)


class TokenSchema(Schema):
    access_token = fields.String(required=True)
    token_type = fields.String(dump_default="bearer")


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = None
        load_instance = True
        include_fk = True


class UserSettingsSchema(Schema):
    key = fields.String(required=True)
    value = fields.String(required=False)


if TYPE_CHECKING:
    CustomDomain = AbstractDomain
    CustomUser = AbstractUser
    CustomUserRole = AbstractUserRole
    CustomToken = AbstractToken
    CustomUserSetting = AbstractUserSetting
else:
    CustomDomain = cast(type[Any], None)
    CustomUser = cast(type[Any], None)
    CustomUserRole = cast(type[Any], None)
    CustomToken = cast(type[Any], None)
    CustomUserSetting = cast(type[Any], None)


@pytest.fixture(scope="module", autouse=True)
def custom_models() -> Iterator[SimpleNamespace]:
    import sys
    import types

    clear_registration()
    db.metadata.clear()
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"
    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    class CustomDomain(AbstractDomain):
        __module__ = module_name
        # Custom fields only - all other fields and table name inherited from AbstractDomain
        domain_type: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)

        def _can_read(self, current_user: CustomUser | None) -> bool:
            """Allow any user to read domains."""
            return True

        def _can_write(self, current_user: CustomUser | None) -> bool:
            """Allow only authenticated users to write domains."""
            return current_user is not None

        def _can_create(self, current_user: CustomUser | None) -> bool:
            """Allow only authenticated users to create domains."""
            return current_user is not None

    class CustomUser(AbstractUser, ProfileMixin):
        __module__ = module_name
        # Custom fields only - all other fields and table name inherited from AbstractUser
        # profile_pic_id is provided by ProfileMixin

        def has_domain_access(self, domain_id: uuid.UUID | None) -> bool:
            if domain_id is None:
                return True
            return any(role.domain_id == domain_id or role.domain_id is None for role in self.roles)

    class CustomUserRole(AbstractUserRole):
        __module__ = module_name
        # All fields and table name inherited from AbstractUserRole
        pass

    class CustomToken(AbstractToken):
        __module__ = module_name
        # All fields and table name inherited from AbstractToken
        pass

    class CustomUserSetting(AbstractUserSetting):
        __module__ = module_name
        # All fields and table name inherited from AbstractUserSetting
        pass

    models = SimpleNamespace(
        CustomDomain=CustomDomain,
        CustomUser=CustomUser,
        CustomUserRole=CustomUserRole,
        CustomToken=CustomToken,
        CustomUserSetting=CustomUserSetting,
    )
    globals().update(models.__dict__)

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
    app.config["API_TITLE"] = "iaoport Integration API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret"
    app.config["JWT_SECRET_KEY"] = "jwt-secret"

    init_fms(
        user=CustomUser,
        role=CustomUserRole,
        token=CustomToken,
        domain=CustomDomain,
        setting=CustomUserSetting,
    )
    init_db(app)
    init_jwt(app)

    # Register error handlers
    RequestHandlers(app)

    return app


class IaoUserBlueprint(UserBlueprint):
    def _validate_login(self, user: CustomUser, data: dict) -> None:  # type: ignore[override]
        if domain_name := data.get("domain"):
            domain = CustomDomain.get_by_or_404(name=domain_name)
            if not user.has_domain_access(domain.id):
                raise UnauthorizedError("No domain access")

    def _register_login_endpoint(self) -> None:
        @self.public_endpoint
        @self.route("/login/", methods=["POST"])
        @self.arguments(LoginArgsSchema)
        @self.response(200, TokenSchema)
        def login(data: dict[str, Any]) -> dict[str, str]:
            with CustomUser.bypass_perms():
                user = CustomUser.get_by(email=data["email"])

            if not user or not user.is_password_correct(data["password"]):
                raise UnauthorizedError("Invalid email or password")
            if not user.is_enabled:
                raise UnauthorizedError("Account disabled")

            self._validate_login(user, data)
            access_token = create_access_token(identity=user.id)
            return {"access_token": access_token, "token_type": "bearer"}

    def _register_current_user_endpoint(self) -> None:
        @self.route("/me", methods=["GET"])
        @self.response(200, UserSchema)
        def get_current_user_profile() -> CustomUser:
            user = CustomUser.get_current_user()
            if not user or not user.id:
                raise UnauthorizedError("Not authenticated")
            return user


@pytest.fixture
def api(app: Flask) -> Api:
    return Api(app)


def test_iaoport_style_integration(app: Flask, api: Api) -> None:
    UserSchema.Meta.model = CustomUser  # type: ignore[assignment]

    class RoleSchema(SQLAlchemyAutoSchema):
        class Meta:
            model = CustomUserRole
            load_instance = True
            include_fk = True

    user_bp = IaoUserBlueprint(
        name="user",
        import_name=__name__,
        url_prefix="/api/user/",
        model=CustomUser,
        schema=UserSchema,
        methods={
            CRUDMethod.INDEX: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.GET: {},
            CRUDMethod.POST: {"admin_only": True, "schema": UserSchema},
            CRUDMethod.DELETE: {},
        },
    )

    role_bp = CRUDBlueprint(
        "user_role",
        __name__,
        url_prefix="<uuid:user_id>/role/",
        model=CustomUserRole,
        schema=RoleSchema,
        methods=[CRUDMethod.INDEX],
    )
    user_bp.register_blueprint(role_bp)

    @user_bp.public_endpoint
    @user_bp.route("token_login", methods=["POST"])
    @user_bp.arguments(TokenLoginArgsSchema)
    @user_bp.response(200, TokenSchema)
    def token_login(data: dict[str, Any]) -> dict[str, str]:
        token = CustomToken.query.filter_by(token=data["token"]).first()
        if not token:
            raise UnauthorizedError("Invalid token")
        if not token.user.is_enabled:
            raise UnauthorizedError("Account disabled")
        if domain_name := data.get("domain"):
            domain = CustomDomain.get_by_or_404(name=domain_name)
            if not token.user.has_domain_access(domain.id):
                raise UnauthorizedError("No domain access")
        access_token = create_access_token(identity=token.user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    @user_bp.route("<uuid:user_id>/settings/", methods=["GET"])
    @user_bp.response(200, UserSettingsSchema(many=True))
    def list_user_settings(user_id: uuid.UUID) -> list[CustomUserSetting]:
        user = CustomUser.get_or_404(user_id)
        if not user.can_write():
            raise UnauthorizedError("Not allowed")
        return CustomUserSetting.query.filter_by(user_id=user_id).all()

    @user_bp.route("<uuid:user_id>/settings/", methods=["POST"])
    @user_bp.arguments(UserSettingsSchema, location="json")
    @user_bp.response(200, UserSettingsSchema(many=True))
    def user_settings(payload: dict[str, Any], user_id: uuid.UUID) -> list[CustomUserSetting]:
        user = CustomUser.get_or_404(user_id)
        if not user.can_write():
            raise UnauthorizedError("Not allowed")
        key = payload["key"]
        setting = CustomUserSetting.get_by(user_id=user_id, key=key)
        if setting:
            setting.value = payload.get("value")
            setting.save()
        else:
            setting = CustomUserSetting(user_id=user_id, key=key, value=payload.get("value"))
            setting.save()
        return CustomUserSetting.query.filter_by(user_id=user_id).all()

    api.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        domain = CustomDomain(name="main", display_name="Main", active=True)
        db.session.add(domain)
        db.session.flush()

        user = CustomUser(email="dave@example.com")
        user.set_password("secret")
        db.session.add(user)
        db.session.flush()

        role = CustomUserRole(user_id=user.id, domain_id=domain.id, role="ADMIN")
        token_value = str(uuid.uuid4())
        token = CustomToken(user_id=user.id, token=token_value)
        db.session.add_all([role, token])
        db.session.commit()

        # Save user.id for later use after commit
        user_id = user.id

    client = app.test_client()
    login_resp = client.post(
        "/api/user/login/",
        json={"email": "dave@example.com", "password": "secret", "domain": "main"},
    )
    assert login_resp.status_code == 200
    jwt_token = login_resp.get_json()["access_token"]

    me_resp = client.get("/api/user/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert me_resp.status_code == 200

    token_login_resp = client.post(
        "/api/user/token_login",
        json={"token": str(uuid.uuid4()), "domain": "main"},
    )
    assert token_login_resp.status_code == 401

    valid_token_resp = client.post(
        "/api/user/token_login",
        json={"token": token_value, "domain": "main"},
    )
    assert valid_token_resp.status_code == 200

    settings_resp = client.post(
        f"/api/user/{user_id}/settings/",
        json={"key": "theme", "value": "dark"},
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert settings_resp.status_code == 200

    role_resp = client.get(
        f"/api/user/{user_id}/role/",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert role_resp.status_code == 200
