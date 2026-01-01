from collections.abc import Generator

import pytest
from flask import Flask

from flask_more_smorest import db, init_db, init_jwt


@pytest.fixture(scope="function")
def app() -> Generator[Flask, None, None]:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    init_db(app)
    init_jwt(app)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
