from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from flask import Flask

from flask_more_smorest import BasePermsModel, db
from flask_more_smorest.error.exceptions import ForbiddenError


@pytest.fixture
def dummy_perms_model(app: Flask) -> type[BasePermsModel]:
    class_name = f"DummyPermsModel_{uuid.uuid4().hex}"

    Dummy = type(
        class_name,
        (BasePermsModel,),
        {
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
    monkeypatch.setattr("flask_more_smorest.perms.user_context.is_current_user_admin", lambda: False)

    with app.app_context():
        instance = dummy_perms_model(name="value")
        instance._can_create = lambda current_user: False  # type: ignore[method-assign]

    with app.test_request_context("/"):
        with pytest.raises(ForbiddenError):
            instance._check_permission("create")


def test_can_write_uses_can_create_when_transient(
    app: Flask, dummy_perms_model: type[BasePermsModel], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr("flask_more_smorest.perms.user_context.is_current_user_admin", lambda: False)
    with app.app_context():
        instance = dummy_perms_model(name="value")

    called: list[str] = []
    instance._can_create = lambda current_user: called.append("create") or True  # type: ignore[method-assign,func-returns-value]
    instance._can_write = lambda current_user: False  # type: ignore[method-assign]

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
    monkeypatch.setattr("flask_more_smorest.perms.user_context.is_current_user_admin", lambda: False)
    with app.app_context():
        instance = dummy_perms_model(name="value")

    called: list[str] = []
    instance._can_create = lambda current_user: False  # type: ignore[method-assign]
    instance._can_write = lambda current_user: called.append("write") or True  # type: ignore[method-assign,func-returns-value]

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


class TestCheckCreateCycles:
    """Tests for permission checking with cyclic relationships."""

    def test_check_create_handles_cycles_without_recursion_error(self, app: Flask) -> None:
        """check_create should gracefully handle cyclic graphs without recursion errors.

        The exact permission outcome is not important here; we only assert that
        a self-referential structure does not cause a RecursionError.
        """

        class Node(BasePermsModel):
            __allow_unmapped__ = True

            id = db.Column(sa.Integer, primary_key=True)
            parent_id = db.Column(sa.Integer, sa.ForeignKey("node.id"))
            parent = db.relationship("Node", remote_side=[id], backref="children")

        with app.app_context():
            db.create_all()

            root = Node()
            # Create a self-cycle
            root.parent = root  # pyright: ignore[reportAttributeAccessIssue]

            # Should not raise RecursionError due to cycle; any permission
            # exceptions would be raised explicitly instead.
            root.check_create([root])
