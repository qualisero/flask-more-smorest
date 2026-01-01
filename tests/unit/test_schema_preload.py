from flask import Flask
from marshmallow import fields

from flask_more_smorest import BaseSchema


class DummySchema(BaseSchema):
    resource_id = fields.String()


def test_preload_injects_view_args() -> None:
    schema = DummySchema()
    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.test_request_context("/resource/123") as ctx:
        ctx.request.view_args = {"resource_id": "123"}
        data = schema.pre_load({}, view_args={}, unknown=None)
        assert data["resource_id"] == "123"
