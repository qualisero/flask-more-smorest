# Flask-More-Smorest

[![PyPI version](https://img.shields.io/pypi/v/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/)
[![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/)
[![Documentation Status](https://readthedocs.org/projects/flask-more-smorest/badge/?version=latest)](https://flask-more-smorest.readthedocs.io/en/latest/)
[![Documentation Status](https://readthedocs.org/projects/flask-more-smorest/badge/?version=stable)](https://flask-more-smorest.readthedocs.io/en/stable/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://img.shields.io/pypi/dm/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/?ts=20260112)

Flask-More-Smorest extends **Flask-Smorest** with a number of enhancements and goodies, with the sole goal of drastically reducing boilerplate and complexity when creating a new REST API with Flask and Flask-Smorest.

**Links:**
- 📦 **PyPI**: https://pypi.org/project/flask-more-smorest/
- 📚 **Documentation**: https://flask-more-smorest.readthedocs.io/
- 🐙 **GitHub**: https://github.com/qualisero/flask-more-smorest

## Highlights

- **Automatic CRUD endpoints** with filtering and pagination
- **SQLAlchemy base model** with auto-generated Marshmallow schemas
- **Built-in user authentication** with JWT and role-based permissions
- **UserBlueprint** for instant login/profile endpoints
- **Resource-based permission management**
- **Health check endpoint** for load balancers and monitoring
- **RFC 7807 error responses** for standardized error handling
- **SQLAlchemy performance monitoring** for identifying slow queries

## Quick Start

```python
from flask import Flask
from flask_more_smorest import BaseModel, CRUDBlueprint, init_db
from flask_more_smorest.perms import Api
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

app = Flask(__name__)
app.config.update(
    API_TITLE="Example API",
    API_VERSION="v1",
    OPENAPI_VERSION="3.0.2",
    SQLALCHEMY_DATABASE_URI="sqlite:///example.db",
    SECRET_KEY="change-me",
    JWT_SECRET_KEY="change-me-too",
)

# Define your model
class Critter(BaseModel):
    name: Mapped[str] = mapped_column(db.String(100))
    species: Mapped[str] = mapped_column(db.String(50))
    cuteness_level: Mapped[int] = mapped_column(db.Integer, default=10)

init_db(app)          # sets up SQLAlchemy
api = Api(app)        # registers JWT + permission hooks

# Create CRUD blueprint using model class directly
critters = CRUDBlueprint(
    "critters",
    __name__,
    model=Critter,           # Use class (preferred over string)
    schema=Critter.Schema,   # Auto-generated schema
    url_prefix="/api/critters/",
)

api.register_blueprint(critters)
```

This automatically creates RESTful endpoints: `GET /api/critters/`, `GET /api/critters/<id>`, `POST /api/critters/`, `PATCH /api/critters/<id>`, `DELETE /api/critters/<id>`, plus automatic filtering (`?created_at__from=...`, `?species=...`) and a health check endpoint at `/health`.

### Controlling endpoints

By default, all CRUD methods are enabled. Control which endpoints are generated:

```python
from flask_more_smorest.crud.crud_blueprint import CRUDMethod

# Enable only specific methods
read_only = CRUDBlueprint(
    "critters",
    __name__,
    model=Critter,
    schema=Critter.Schema,
    methods=[CRUDMethod.INDEX, CRUDMethod.GET],  # Only list and get
)

# Disable specific methods
no_delete = CRUDBlueprint(
    "critters",
    __name__,
    model=Critter,
    schema=Critter.Schema,
    skip_methods=[CRUDMethod.DELETE],  # All except delete
)
```

For advanced configuration (custom schemas, admin-only endpoints, etc.), see the [full documentation](https://flask-more-smorest.readthedocs.io/).

## Working with models

Use `BaseModel` for simple models with UUID keys, timestamp tracking, and auto-generated Marshmallow schemas:

```python
from flask_more_smorest import BaseModel
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

class Critter(BaseModel):
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    species: Mapped[str] = mapped_column(db.String(50), nullable=False)
    cuteness_level: Mapped[int] = mapped_column(db.Integer, default=10)
```

**Auto-generated schema:** `Critter.Schema` is automatically created with all fields. Use it directly in blueprints—no need to define custom schemas unless you need special validation.

### Adding permission checks

Use `BasePermsModel` when you need permission hooks:

```python
from flask_more_smorest.perms import BasePermsModel
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

class Critter(BasePermsModel):
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    species: Mapped[str] = mapped_column(db.String(50), nullable=False)

    def _can_write(self) -> bool:
        return self.is_current_user_admin()

    def _can_read(self) -> bool:
        return True  # Anyone can read
```

`BasePermsModel` adds `_can_read()`, `_can_write()`, and `_can_create()` hooks that are checked automatically on CRUD operations.

## Built-in user authentication

Get instant authentication with `UserBlueprint`:

```python
from flask_more_smorest import UserBlueprint

# Instant login and profile endpoints
user_bp = UserBlueprint()  # Creates /api/users/login/ and /api/users/me/
api.register_blueprint(user_bp)
```

This provides:
- `POST /api/users/login/` - JWT authentication
- `GET /api/users/me/` - Current user profile
- Full CRUD for user management
- Role-based permissions

### Extending the User model

Add custom fields by inheriting from `User`:

```python
from flask_more_smorest import User, UserBlueprint
from flask_more_smorest.sqla import db
from sqlalchemy.orm import Mapped, mapped_column

class Employee(User):
    employee_id: Mapped[str] = mapped_column(db.String(32), unique=True)
    department: Mapped[str] = mapped_column(db.String(100))

# Use custom user model in blueprint
employee_bp = UserBlueprint(model=Employee, schema=Employee.Schema)
```

### Enable public registration

```python
class PublicUser(User):
    PUBLIC_REGISTRATION = True  # Allow unauthenticated user creation

public_bp = UserBlueprint(model=PublicUser, schema=PublicUser.Schema)
```

### Using your own User model

If you already have a User model, configure flask-more-smorest to use it:

```python
from flask_more_smorest.perms import register_get_current_user, register_get_current_user_id
from my_app.auth import get_current_user, get_current_user_id

register_get_current_user(get_current_user)
register_get_current_user_id(get_current_user_id)
# Permission system now uses your User model
```

See [Custom User Context](https://flask-more-smorest.readthedocs.io/en/latest/custom-user-context.html) for details.

## Production Features

### Health Check Endpoint

Built-in health check for load balancers and monitoring systems:

```bash
curl http://localhost:5000/health
```

```json
{
  "status": "healthy",
  "timestamp": "2026-01-11T08:30:00+00:00",
  "version": "0.6.0",
  "database": "connected"
}
```

Configure via `HEALTH_ENDPOINT_PATH` and `HEALTH_ENDPOINT_ENABLED`.

### RFC 7807 Error Responses

Standardized error format following [RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807):

```json
{
  "type": "/errors/not_found_error",
  "title": "Not Found",
  "status": 404,
  "detail": "User with id 123 doesn't exist",
  "instance": "/api/users/123"
}
```

Debug information automatically included in debug/testing mode only.

### SQLAlchemy Performance Monitoring

Track and log slow queries:

```python
app.config.update(
    SQLALCHEMY_PERFORMANCE_MONITORING=True,
    SQLALCHEMY_SLOW_QUERY_THRESHOLD=0.5,  # Log queries over 500ms
)
```

Get per-request statistics:

```python
from flask_more_smorest.sqla import get_request_query_stats

@app.after_request
def log_stats(response):
    stats = get_request_query_stats()
    print(f"Queries: {stats['query_count']}, Time: {stats['total_query_time']:.3f}s")
    return response
```

## Learn more

- 📚 **Documentation**: https://flask-more-smorest.readthedocs.io/
- 📦 **PyPI Package**: https://pypi.org/project/flask-more-smorest/
- 🔧 **API Reference**: Full API documentation and guides available in docs
- 💡 **Examples**: The `tests/` directory demonstrates filters, permissions, and pagination end-to-end

## Contributing

Contributions and feedback are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
