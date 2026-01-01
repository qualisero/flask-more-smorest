from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from _pytest.monkeypatch import MonkeyPatch
from flask import Flask

from flask_more_smorest import BasePermsModel, db
from flask_more_smorest.error.exceptions import ForbiddenError


@pytest.fixture(scope="function")
def dummy_perms_model(app: Flask) -> type[BasePermsModel]:
    table_name = f"dummy_perms_models_{uuid.uuid4().hex}"
    class_name = f"DummyPermsModel_{uuid.uuid4().hex}"

    Dummy = type(
        class_name,
        (BasePermsModel,),
        {
            "__tablename__": table_name,
            "__module__": __name__,
            "name": db.Column(db.String(30), nullable=False),
        },
    )

    with app.app_context():
        db.create_all()
    return Dummy


def test_check_permission_raises_for_create(
    app: Flask, dummy_perms_model: type[BasePermsModel], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(BasePermsModel, "is_current_user_admin", classmethod(lambda cls: False))

    with app.app_context():
        instance = dummy_perms_model(name="value")
        instance._can_create = lambda: False  # type: ignore[method-assign]

    with app.test_request_context("/"):
        with pytest.raises(ForbiddenError):
            instance._check_permission("create")


def test_can_write_uses_can_create_when_transient(
    app: Flask, dummy_perms_model: type[BasePermsModel], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(BasePermsModel, "is_current_user_admin", classmethod(lambda cls: False))
    with app.app_context():
        instance = dummy_perms_model(name="value")

    called: list[str] = []
    instance._can_create = lambda: called.append("create") or True  # type: ignore[method-assign,func-returns-value]
    instance._can_write = lambda: False  # type: ignore[method-assign]

    def fake_inspect(obj: object) -> object:
        @dataclass
        class State:
            transient: bool = True
            pending: bool = False

        return State()

    monkeypatch.setattr("flask_more_smorest.perms.base_perms_model.sa.inspect", fake_inspect)

    with app.test_request_context("/"):
        assert instance.can_write()

    assert called == ["create"]


def test_can_write_uses_write_when_persisted(
    app: Flask, dummy_perms_model: type[BasePermsModel], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(BasePermsModel, "is_current_user_admin", classmethod(lambda cls: False))
    with app.app_context():
        instance = dummy_perms_model(name="value")

    called: list[str] = []
    instance._can_create = lambda: False  # type: ignore[method-assign]
    instance._can_write = lambda: called.append("write") or True  # type: ignore[method-assign,func-returns-value]

    def fake_inspect(obj: object) -> object:
        @dataclass
        class State:
            transient: bool = False
            pending: bool = False

        return State()

    monkeypatch.setattr("flask_more_smorest.perms.base_perms_model.sa.inspect", fake_inspect)

    with app.test_request_context("/"):
        assert instance.can_write()

    assert called == ["write"]


def test_is_current_user_admin_handles_runtime_error(monkeypatch: MonkeyPatch) -> None:
    def raise_runtime_error(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("no context")

    monkeypatch.setattr("flask_more_smorest.perms.base_perms_model.verify_jwt_in_request", raise_runtime_error)

    assert BasePermsModel.is_current_user_admin() is False
