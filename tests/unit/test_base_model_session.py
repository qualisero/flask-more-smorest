from __future__ import annotations

import sqlalchemy as sa
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import BaseModel, db


class SimpleModel(BaseModel):
    name: Mapped[str] = mapped_column(sa.String(50))


def test_base_model_allows_inactive_session(app: Flask) -> None:
    with app.app_context():
        db.create_all()

        instance = SimpleModel(name="first")
        instance.save()
        db.session.commit()
        db.session.close()

        # Session is closed (inactive). New instances should still be creatable.
        other = SimpleModel(name="second")
        assert other.name == "second"
