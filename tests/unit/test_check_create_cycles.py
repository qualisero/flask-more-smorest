from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import Flask

from flask_more_smorest.perms.base_perms_model import BasePermsModel
from flask_more_smorest.sqla.database import db

if TYPE_CHECKING:  # pragma: no cover
    pass


class Node(BasePermsModel):
    __tablename__ = "node_check_create_cycle"
    __allow_unmapped__ = True

    id = db.Column(sa.Integer, primary_key=True)
    parent_id = db.Column(sa.Integer, sa.ForeignKey("node_check_create_cycle.id"))
    parent = db.relationship("Node", remote_side=[id], backref="children")


def test_check_create_handles_cycles_without_recursion_error(app: Flask) -> None:
    """check_create should gracefully handle cyclic graphs without recursion errors.

    The exact permission outcome is not important here; we only assert that
    a self-referential structure does not cause a RecursionError.
    """

    with app.app_context():
        db.create_all()

        root = Node()
        # Create a self-cycle
        root.parent = root  # pyright: ignore[reportAttributeAccessIssue]

        # Should not raise RecursionError due to cycle; any permission
        # exceptions would be raised explicitly instead.
        root.check_create([root])
