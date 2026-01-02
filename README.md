# Flask-More-Smorest

[![PyPI version](https://badge.fury.io/py/flask-more-smorest.svg?v=0.2.2)](https://badge.fury.io/py/flask-more-smorest)
[![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg?v=0.2.2)](https://pypi.org/project/flask-more-smorest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Flask-More-Smorest extends **Flask-Smorest** with a number of enhancements and goodies, with the sole goal of drastically reducing boilerplate and complexity when creating a new REST API.

## Highlights

- Automatic CRUD endpoints with filtering and pagination
- SQLAlchemy base model with Marshmallow schemas
- User management
- Resource-based permission management

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

critters = CRUDBlueprint(
    "critters",
    __name__,
    model="Critter",        # resolved from your models module
    schema="CritterSchema",  # resolved from your schemas module
    url_prefix="/api/critters/",
)

api.register_blueprint(critters)
```

The blueprint above exposes the usual REST operations (`GET`, `POST`, `PATCH`, `DELETE`) plus automatic filtering (`/api/critters/?created_at__from=...`).

### Controlling generated endpoints

Control which CRUD routes are created using the `methods` parameter:

```python
from flask_more_smorest.crud.crud_blueprint import CRUDMethod

# All methods enabled by default
critters = CRUDBlueprint(
    "critters",
    __name__,
    model="Critter",
    schema="CritterSchema",
)

# Enable only specific methods (whitelist)
critters = CRUDBlueprint(
    "critters",
    __name__,
    model="Critter",
    schema="CritterSchema",
    methods=[CRUDMethod.INDEX, CRUDMethod.GET],
)

# Customize or disable specific methods (all enabled by default with dict)
critters = CRUDBlueprint(
    "critters",
    __name__,
    model="Critter",
    schema="CritterSchema",
    methods={
        CRUDMethod.POST: {"schema": "CritterWriteSchema"},  # Custom schema
        CRUDMethod.DELETE: {"admin_only": True},            # Admin-only endpoint
        CRUDMethod.PATCH: False,                            # Disable this method
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

class Critter(BaseModel):
    # __tablename__ auto-generated as "critter"
    
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    species: Mapped[str] = mapped_column(db.String(50), nullable=False)
    cuteness_level: Mapped[int] = mapped_column(db.Integer, default=10)

    def _can_write(self) -> bool:  # optional permission hook
        return self.is_current_user_admin()
```

`Critter.Schema()` instantly provides a Marshmallow schema (including an `is_writable` field) ready for use in blueprints.

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
    # Inherits User's table (single table inheritance)
    # Use __tablename__ = "employees" for separate table
    employee_id: Mapped[str] = mapped_column(db.String(32), unique=True)
```

## Learn more

- 📚 **Documentation**: [ReadTheDocs](https://flask-more-smorest.readthedocs.io/en/stable/) (stable) or [latest](https://flask-more-smorest.readthedocs.io/en/latest/) (dev)
- 🔧 **API Reference**: Full API documentation and guides available online
- 💡 **Examples**: The `tests/` directory demonstrates filters, permissions, and pagination end-to-end

## Release Process

**Creating a new release:**
```bash
./scripts/bump_version.sh [patch|minor|major]  # Updates version and provides next steps
# Then: update CHANGELOG.md, commit, tag, and create GitHub release
```
GitHub Actions automatically publishes to PyPI and updates ReadTheDocs.

Contributions and feedback are welcome—see [CONTRIBUTING.md](CONTRIBUTING.md) for details.
