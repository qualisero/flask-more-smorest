# Flask-More-Smorest

[![PyPI version](https://badge.fury.io/py/flask-more-smorest.svg)](https://badge.fury.io/py/flask-more-smorest)
[![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Flask-More-Smorest extends **Flask-Smorest** with batteries-included CRUD blueprints, SQLAlchemy helpers, and an opinionated user/permission system.

## Highlights

- Automatic CRUD endpoints with filtering and pagination
- Blueprint mixins for public/admin annotations and operation IDs
- SQLAlchemy base model with Marshmallow schemas and permission hooks
- Optional JWT-powered user, role, and token models

## Quick Start

```python
from flask import Flask
from flask_more_smorest import init_db
from flask_more_smorest.perms import Api, CRUDBlueprint

app = Flask(__name__)
app.config.update(
    API_TITLE="Example API",
    API_VERSION="v1",
    OPENAPI_VERSION="3.0.2",
    SQLALCHEMY_DATABASE_URI="sqlite:///example.db",
    SECRET_KEY="change-me",
    JWT_SECRET_KEY="change-me-too",
)

init_db(app)          # sets up SQLAlchemy
api = Api(app)        # registers JWT + permission hooks

users = CRUDBlueprint(
    "users",
    __name__,
    model="User",        # resolved from your models module
    schema="UserSchema",  # resolved from your schemas module
    url_prefix="/api/users/",
)

api.register_blueprint(users)
```

The blueprint above exposes the usual REST operations (`GET`, `POST`, `PATCH`, `DELETE`) plus automatic filtering (`/api/users/?created_at__from=...`).

### Controlling generated endpoints

Control which CRUD routes are created using the `methods` parameter:

```python
from flask_more_smorest.crud.crud_blueprint import CRUDMethod

# All methods enabled by default
users = CRUDBlueprint(
    "users",
    __name__,
    model="User",
    schema="UserSchema",
)

# Enable only specific methods (whitelist)
users = CRUDBlueprint(
    "users",
    __name__,
    model="User",
    schema="UserSchema",
    methods=[CRUDMethod.INDEX, CRUDMethod.GET],
)

# Customize or disable specific methods (all enabled by default with dict)
users = CRUDBlueprint(
    "users",
    __name__,
    model="User",
    schema="UserSchema",
    methods={
        CRUDMethod.POST: {"schema": "UserWriteSchema"},  # Custom schema
        CRUDMethod.DELETE: {"admin_only": True},         # Admin-only endpoint
        CRUDMethod.PATCH: False,                         # Disable this method
        # INDEX and GET not mentioned → enabled with defaults
    },
)
```

**When using a dict, all methods are enabled by default.** Specify a method to customize it, or set it to `False` to disable.

## Working with models

Use `BaseModel` to get UUID keys, timestamp fields, and auto-generated Marshmallow schemas:

```python
from flask_more_smorest import BaseModel
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

class Article(BaseModel):
    __tablename__ = "article"

    title: Mapped[str] = mapped_column(db.String(200), nullable=False)
    body: Mapped[str] = mapped_column(db.Text, nullable=False)

    def _can_write(self) -> bool:  # optional permission hook
        return self.is_current_user_admin()
```

`Article.Schema()` instantly provides a Marshmallow schema (including an `is_writable` field) ready for use in blueprints.

## Built-in user system

Import the ready-made models when you need authentication, roles, or tokens:

```python
from flask_more_smorest.perms import DefaultUserRole, User, UserRole

user = User(email="admin@example.com")
user.set_password("secret")
user.save()

UserRole(user=user, role=DefaultUserRole.ADMIN).save()
```

Extending the default user is straightforward—inherit from `User` and add your fields or mixins:

```python
from flask_more_smorest.perms import ProfileMixin, TimestampMixin, User
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

class Employee(User, ProfileMixin, TimestampMixin):
    __tablename__ = "employee"
    employee_id: Mapped[str] = mapped_column(db.String(32), unique=True)
```

## Learn more

- API reference and guides: [project documentation](https://github.com/qualisero/flask-more-smorest#readme)
- Examples and tests under the `tests/` directory demonstrate filters, permissions, and pagination end-to-end.

Contributions and feedback are welcome—see [CONTRIBUTING.md](CONTRIBUTING.md) for details.
