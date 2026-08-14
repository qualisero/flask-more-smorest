"""Integration tests for arg_schema on POST and PATCH CRUD endpoints.

Verifies that:
- POST: arg_schema is used for request input; schema is used for response output.
- POST: when no arg_schema is given, schema is used for both (backwards-compatible).
- PATCH: arg_schema is used for the update payload (existing behaviour).
"""

from __future__ import annotations

import contextlib
import sys
import types
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.ext.marshmallow import resolver as default_resolver
from flask import Flask
from flask_smorest import Api
from marshmallow import Schema, ValidationError, fields, validates

from flask_more_smorest import BaseModel, CRUDBlueprint, CRUDMethod, db, init_db
from flask_more_smorest.crud.crud_blueprint import MethodConfig
from flask_more_smorest.perms import init_fms

if TYPE_CHECKING:
    from flask.testing import FlaskClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def custom_schema_name_resolver(schema: type[Schema], **kwargs: str | bool) -> str:
    """Append 'Partial' for partial schemas to avoid apispec name collisions."""
    if getattr(schema, "partial", False):
        return default_resolver(schema) + "Partial"
    return default_resolver(schema)


def make_app() -> Flask:
    from flask_more_smorest.perms import clear_registration
    from flask_more_smorest.perms.models import defaults as defaults_module

    clear_registration()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "arg_schema Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key-arg-schema"

    init_fms(
        user=defaults_module.User,
        role=defaults_module.UserRole,
        token=defaults_module.Token,
        domain=defaults_module.Domain,
        setting=defaults_module.UserSetting,
    )
    init_db(app)
    return app


def make_api(app: Flask) -> Api:
    ma_plugin = MarshmallowPlugin(schema_name_resolver=custom_schema_name_resolver)
    return Api(app, spec_kwargs={"marshmallow_plugin": ma_plugin})


def _always_allowed(_self: Any) -> bool:
    """Permission hook for test models: everything is permitted."""
    return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def item_model(tmp_path: object) -> type[BaseModel]:
    """Create a simple Item model for testing arg_schema on POST."""
    rand_str = uuid.uuid4().hex
    class_name = f"Item_{rand_str}"

    ItemModel = type(
        class_name,
        (BaseModel,),
        {
            "__module__": __name__,
            "name": db.Column(db.String(100), nullable=False),
            "secret_code": db.Column(db.String(50), nullable=True),
            "public_note": db.Column(db.String(200), nullable=True),
            "_can_read": _always_allowed,
            "_can_write": _always_allowed,
            "_can_create": classmethod(_always_allowed),
        },
    )

    app = make_app()
    with app.app_context():
        db.create_all()

    ItemModel._test_app = app
    return ItemModel


@pytest.fixture
def patch_model(tmp_path: object) -> type[BaseModel]:
    """Create a simple Widget model for testing arg_schema on PATCH."""
    rand_str = uuid.uuid4().hex
    class_name = f"Widget_{rand_str}"

    WidgetModel = type(
        class_name,
        (BaseModel,),
        {
            "__module__": __name__,
            "name": db.Column(db.String(100), nullable=False),
            "internal_value": db.Column(db.Integer, nullable=True),
            "public_value": db.Column(db.Integer, nullable=True),
            "_can_read": _always_allowed,
            "_can_write": _always_allowed,
            "_can_create": classmethod(_always_allowed),
        },
    )

    app = make_app()
    with app.app_context():
        db.create_all()

    WidgetModel._test_app = app
    return WidgetModel


# ---------------------------------------------------------------------------
# Test: POST arg_schema
# ---------------------------------------------------------------------------


class TestPostArgSchema:
    """POST endpoint honours arg_schema for input and schema for response."""

    def _make_client(
        self,
        item_model: type[BaseModel],
        *,
        with_arg_schema: bool,
    ) -> tuple[FlaskClient, Flask, type[Schema], type[Schema]]:
        """Build a test client with or without arg_schema on POST."""
        rand_str = uuid.uuid4().hex
        module_name = f"mock_arg_schema_{rand_str}"

        # Input schema: requires name + secret_code; rejects anything else
        class InputSchema(Schema):
            name = fields.Str(required=True)
            secret_code = fields.Str(required=True)

            @validates("secret_code")
            def validate_secret(self, value: str) -> None:
                if value != "open-sesame":
                    raise ValidationError("Invalid secret code.")

        InputSchema.__name__ = f"InputSchema_{rand_str}"
        InputSchema.__qualname__ = InputSchema.__name__

        # Response schema: returns name + public_note only (no secret_code)
        class ResponseSchema(Schema):
            id = fields.Str(dump_only=True)
            name = fields.Str()
            public_note = fields.Str()

        ResponseSchema.__name__ = f"ResponseSchema_{rand_str}"
        ResponseSchema.__qualname__ = ResponseSchema.__name__

        # Register schemas and model in a temporary module
        mock_module = types.ModuleType(module_name)
        setattr(mock_module, item_model.__name__, item_model)
        setattr(mock_module, InputSchema.__name__, InputSchema)
        setattr(mock_module, ResponseSchema.__name__, ResponseSchema)
        sys.modules[module_name] = mock_module

        methods: dict[CRUDMethod, MethodConfig] = {
            CRUDMethod.POST: {
                "schema": ResponseSchema,
            }
        }
        if with_arg_schema:
            methods[CRUDMethod.POST]["arg_schema"] = InputSchema

        bp = CRUDBlueprint(
            f"items_{rand_str}",
            __name__,
            model=item_model,
            schema=item_model.Schema,
            methods=methods,
            url_prefix=f"/api/items_{rand_str}/",
        )

        app = item_model._test_app
        api = make_api(app)
        api.register_blueprint(bp)
        client = app.test_client()
        return client, app, InputSchema, ResponseSchema

    def _post_url(self, app: Flask) -> str:
        """Find the POST collection URL registered by the blueprint."""
        rules = [r for r in app.url_map.iter_rules() if "items_" in r.rule and r.methods and "POST" in r.methods]
        assert rules, "No POST rule registered"
        # Collection URL has no path parameters; return it directly.
        return rules[0].rule

    def test_post_with_arg_schema_accepts_valid_input(self, item_model: type[BaseModel]) -> None:
        """When arg_schema is set, valid input matching arg_schema is accepted."""
        client, app, _InputSchema, _ResponseSchema = self._make_client(item_model, with_arg_schema=True)

        with app.app_context():
            with item_model.bypass_perms():
                url = self._post_url(app)
                resp = client.post(url, json={"name": "Aladdin", "secret_code": "open-sesame"})
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["name"] == "Aladdin"
                # Response schema omits secret_code
                assert "secret_code" not in data
                # The row is actually persisted, with the arg_schema-only field
                rows = item_model.query.all()
                assert len(rows) == 1
                assert rows[0].name == "Aladdin"
                assert rows[0].secret_code == "open-sesame"

    def test_post_with_arg_schema_rejects_invalid_secret(self, item_model: type[BaseModel]) -> None:
        """arg_schema validation runs: wrong secret_code yields 422."""
        client, app, _InputSchema, _ResponseSchema = self._make_client(item_model, with_arg_schema=True)

        with app.app_context():
            with item_model.bypass_perms():
                url = self._post_url(app)
                resp = client.post(url, json={"name": "Aladdin", "secret_code": "wrong"})
                assert resp.status_code == 422

    def test_post_with_arg_schema_rejects_missing_secret(self, item_model: type[BaseModel]) -> None:
        """arg_schema is enforced: missing secret_code field yields 422."""
        client, app, _InputSchema, _ResponseSchema = self._make_client(item_model, with_arg_schema=True)

        with app.app_context():
            with item_model.bypass_perms():
                url = self._post_url(app)
                # Only name, no secret_code
                resp = client.post(url, json={"name": "Aladdin"})
                assert resp.status_code == 422

    def test_post_without_arg_schema_uses_schema_for_both(self, item_model: type[BaseModel]) -> None:
        """Without arg_schema, schema is used for both input and response (backwards compat)."""
        client, app, _InputSchema, _ResponseSchema = self._make_client(item_model, with_arg_schema=False)

        with app.app_context():
            with item_model.bypass_perms():
                url = self._post_url(app)
                # ResponseSchema only requires name (no secret_code), so this succeeds
                resp = client.post(url, json={"name": "Ali Baba"})
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["name"] == "Ali Baba"
                rows = item_model.query.all()
                assert len(rows) == 1
                assert rows[0].name == "Ali Baba"

    def test_post_with_plain_arg_schema_ignores_non_model_fields(self, item_model: type[BaseModel]) -> None:
        """The documented invite-only signup shape: a validated field with no column.

        arg_schema exists precisely to accept an input shape that differs from the
        model, so a field the model does not define must be validated and then
        dropped, not passed to the declarative constructor.
        """
        rand_str = uuid.uuid4().hex

        class InviteSignupSchema(Schema):
            name = fields.Str(required=True)
            invite_code = fields.Str(required=True, load_only=True)

            @validates("invite_code")
            def validate_invite(self, value: str) -> None:
                if value != "open-sesame":
                    raise ValidationError("Invalid invite code.")

        InviteSignupSchema.__name__ = f"InviteSignupSchema_{rand_str}"
        InviteSignupSchema.__qualname__ = InviteSignupSchema.__name__

        class PublicSchema(Schema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

        PublicSchema.__name__ = f"PublicSchema_{rand_str}"
        PublicSchema.__qualname__ = PublicSchema.__name__

        bp = CRUDBlueprint(
            f"items_{rand_str}",
            __name__,
            model=item_model,
            schema=item_model.Schema,
            methods={CRUDMethod.POST: {"arg_schema": InviteSignupSchema, "schema": PublicSchema}},
            url_prefix=f"/api/items_{rand_str}/",
        )

        app = item_model._test_app
        api = make_api(app)
        api.register_blueprint(bp)
        client = app.test_client()

        with app.app_context(), item_model.bypass_perms():
            url = self._post_url(app)
            # The invite code is enforced
            assert client.post(url, json={"name": "Morgiana", "invite_code": "wrong"}).status_code == 422
            resp = client.post(url, json={"name": "Morgiana", "invite_code": "open-sesame"})
            assert resp.status_code == 200
            assert resp.get_json()["name"] == "Morgiana"
            rows = item_model.query.all()
            assert len(rows) == 1
            assert rows[0].name == "Morgiana"
            assert not hasattr(rows[0], "invite_code")

    def test_post_with_model_bound_arg_schema_persists(self, item_model: type[BaseModel]) -> None:
        """A model-bound arg_schema (load_instance=True) also creates the resource."""
        rand_str = uuid.uuid4().hex

        class BoundInputSchema(item_model.Schema):
            invite_code = fields.Str(required=True, load_only=True)

            @validates("invite_code")
            def validate_invite(self, value: str) -> None:
                if value != "open-sesame":
                    raise ValidationError("Invalid invite code.")

        BoundInputSchema.__name__ = f"BoundInputSchema_{rand_str}"
        BoundInputSchema.__qualname__ = BoundInputSchema.__name__

        class BoundResponseSchema(Schema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

        BoundResponseSchema.__name__ = f"BoundResponseSchema_{rand_str}"
        BoundResponseSchema.__qualname__ = BoundResponseSchema.__name__

        bp = CRUDBlueprint(
            f"items_{rand_str}",
            __name__,
            model=item_model,
            schema=item_model.Schema,
            methods={
                CRUDMethod.POST: {
                    "arg_schema": BoundInputSchema,
                    "schema": BoundResponseSchema,
                }
            },
            url_prefix=f"/api/items_{rand_str}/",
        )

        app = item_model._test_app
        api = make_api(app)
        api.register_blueprint(bp)
        client = app.test_client()

        with app.app_context():
            with item_model.bypass_perms():
                url = self._post_url(app)
                assert client.post(url, json={"name": "Morgiana"}).status_code == 422
                resp = client.post(url, json={"name": "Morgiana", "invite_code": "open-sesame"})
                assert resp.status_code == 200
                assert "invite_code" not in resp.get_json()
                rows = item_model.query.all()
                assert len(rows) == 1
                assert rows[0].name == "Morgiana"


# ---------------------------------------------------------------------------
# Test: PATCH arg_schema (existing behaviour)
# ---------------------------------------------------------------------------


class TestPatchArgSchema:
    """PATCH endpoint honours arg_schema (existing behaviour, now explicitly tested)."""

    def _make_patch_client(self, patch_model: type[BaseModel]) -> tuple[FlaskClient, Flask]:
        """Build a test client with arg_schema on PATCH."""
        rand_str = uuid.uuid4().hex
        module_name = f"mock_patch_arg_schema_{rand_str}"

        # Restricted update schema: only public_value can be changed via this endpoint
        class PatchInputSchema(Schema):
            public_value = fields.Int(required=True)

        PatchInputSchema.__name__ = f"PatchInputSchema_{rand_str}"
        PatchInputSchema.__qualname__ = PatchInputSchema.__name__

        mock_module = types.ModuleType(module_name)
        setattr(mock_module, patch_model.__name__, patch_model)
        setattr(mock_module, PatchInputSchema.__name__, PatchInputSchema)
        sys.modules[module_name] = mock_module

        bp = CRUDBlueprint(
            f"widgets_{rand_str}",
            __name__,
            model=patch_model,
            schema=patch_model.Schema,
            methods={
                CRUDMethod.POST: True,
                CRUDMethod.GET: True,
                CRUDMethod.PATCH: {"arg_schema": PatchInputSchema},
            },
            url_prefix=f"/api/widgets_{rand_str}/",
        )

        app = patch_model._test_app
        api = make_api(app)
        api.register_blueprint(bp)
        return app.test_client(), app

    def _patch_url(self, app: Flask, widget_id: str) -> str:
        """Resolve the PATCH URL for the widget resource."""
        rules = [r for r in app.url_map.iter_rules() if "widgets_" in r.rule and r.methods and "PATCH" in r.methods]
        assert rules, "No PATCH rule registered"
        # Rule looks like /api/widgets_xxx/<uuid:widgets_xxx_id>
        # Replace the converter placeholder with the actual widget id.
        rule = rules[0].rule
        import re

        return re.sub(r"<[^>]+>", widget_id, rule)

    def test_patch_arg_schema_accepts_valid_payload(self, patch_model: type[BaseModel]) -> None:
        """PATCH with arg_schema: valid payload succeeds."""
        client, app = self._make_patch_client(patch_model)

        with app.app_context():
            with patch_model.bypass_perms():
                widget = patch_model(name="Widget", internal_value=99, public_value=0)
                db.session.add(widget)
                db.session.commit()
                widget_id = str(widget.id)

                url = self._patch_url(app, widget_id)
                resp = client.patch(url, json={"public_value": 42})
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["public_value"] == 42
                assert data["internal_value"] == 99  # unchanged

    def test_patch_arg_schema_rejects_extra_fields(self, patch_model: type[BaseModel]) -> None:
        """PATCH arg_schema: unknown fields are rejected (flask-smorest default RAISE)."""
        client, app = self._make_patch_client(patch_model)

        with app.app_context():
            with patch_model.bypass_perms():
                widget = patch_model(name="Widget2", internal_value=5, public_value=0)
                db.session.add(widget)
                db.session.commit()
                widget_id = str(widget.id)

                url = self._patch_url(app, widget_id)
                # Attempt to patch internal_value which is not in PatchInputSchema
                resp = client.patch(url, json={"public_value": 1, "internal_value": 999})
                # Unknown fields are rejected
                assert resp.status_code == 422


@pytest.fixture(scope="module", autouse=True)
def _module_cleanup() -> Iterator[None]:
    """Clean up at module boundaries to prevent registry pollution."""
    yield
    from flask_more_smorest.perms import clear_registration

    clear_registration()
    db.metadata.clear()

    with contextlib.suppress(Exception):
        sa.orm.clear_mappers()
