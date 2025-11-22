# Flask-More-Smorest

[![PyPI version](https://badge.fury.io/py/flask-more-smorest.svg)](https://badge.fury.io/py/flask-more-smorest)
[![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A powerful extension library for Flask-Smorest that provides automatic CRUD operations, enhanced blueprints with annotations, advanced query filtering capabilities, and comprehensive permission-based database models.

## Features

- 🚀 **Automatic CRUD Operations**: Generate complete RESTful APIs with minimal code
- 📝 **Enhanced Blueprints**: Additional decorators for public/admin endpoints
- 🔍 **Advanced Query Filtering**: Automatic filtering with range queries for dates
- 🏷️ **Operation ID Generation**: Automatic OpenAPI operationId generation
- 🔐 **Permission-Based Models**: BaseModel with built-in permission checking and user context
- 👤 **User Management**: Complete User/UserRole/UserSetting models with authentication
- 🛡️ **Security Features**: JWT integration, password hashing, role-based access control
- 📊 **Auto-Generated Schemas**: Dynamic Marshmallow schemas with permission fields
- 🐍 **Modern Python**: Full type hints and Python 3.11+ support
- ⚡ **SQLAlchemy 2.0**: Built for the latest SQLAlchemy patterns

## Quick Start

### Installation

```bash
pip install flask-more-smorest
```

### Basic Usage

```python
from flask import Flask
from flask_smorest import Api
from flask_more_smorest import CRUDBlueprint
from flask_more_smorest.database import db

app = Flask(__name__)
app.config['API_TITLE'] = 'My API'
app.config['API_VERSION'] = 'v1'
app.config['OPENAPI_VERSION'] = '3.0.2'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
app.config['SECRET_KEY'] = 'your-secret-key'

# Initialize database
db.init_app(app)
api = Api(app)

# Create a CRUD blueprint for your User model
users_blp = CRUDBlueprint(
    'users', __name__,
    model='User',           # Your SQLAlchemy model name
    schema='UserSchema',    # Your Marshmallow schema name
    url_prefix='/api/users/'
)

api.register_blueprint(users_blp)
```

This automatically creates the following endpoints:

- `GET /api/users/` - List all users (with filtering)
- `POST /api/users/` - Create a new user
- `GET /api/users/{user_id}` - Get a specific user
- `PATCH /api/users/{user_id}` - Update a user
- `DELETE /api/users/{user_id}` - Delete a user

### Enhanced Blueprints

```python
from flask_more_smorest import EnhancedBlueprint

# Regular enhanced blueprint with annotations
blp = EnhancedBlueprint('auth', __name__)

@blp.route('/login', methods=['POST'])
@blp.public_endpoint
def login():
    \"\"\"User login endpoint\"\"\"
    # This endpoint is marked as public in documentation
    pass

@blp.route('/admin/stats', methods=['GET'])
@blp.admin_endpoint  
def admin_stats():
    \"\"\"Get admin statistics\"\"\"
    # This endpoint is marked as admin-only in documentation
    pass
```

### BaseModel Features

The library provides a powerful `BaseModel` class with built-in permissions and user context:

```python
from flask_more_smorest import BaseModel
from flask_more_smorest.database import db
from sqlalchemy.orm import Mapped, mapped_column

class Post(BaseModel):
    """Blog post model with automatic permissions."""
    
    title: Mapped[str] = mapped_column(db.String(200), nullable=False)
    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    published: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    def _can_write(self):
        """Only post author or admin can modify."""
        return self.created_by == current_user.id or current_user.is_admin
    
    def _can_read(self):
        """Anyone can read published posts, author can read drafts."""
        return self.published or self._can_write()

# Automatic schema generation with permission fields
post_schema = Post.Schema()  # Includes 'is_writable' field
```

### User Management and Customization

Complete user management system with simple customization through inheritance:

```python
from flask_more_smorest import User
from flask_more_smorest.user import UserRole, UserSetting, ProfileMixin

# Use the default User model as-is
user = User(email="user@example.com", password="secret123")
user.save()

# Or extend User with custom fields and behavior
class CustomUser(User):
    bio: Mapped[str | None] = mapped_column(db.String(500))
    department: Mapped[str] = mapped_column(db.String(100))
    
    # Override permission methods if needed
    def _can_write(self) -> bool:
        return self.department == "Engineering" and super()._can_write()

# Use provided mixins for common functionality
class EnhancedUser(User, ProfileMixin):
    # Inherits first_name, last_name, display_name, avatar_url from ProfileMixin
    security_level: Mapped[int] = mapped_column(db.Integer, default=1)
    
    @property
    def is_admin(self) -> bool:
        return self.security_level >= 8 or super().is_admin

# Role-based permissions work automatically
admin_role = UserRole(user=user, role=UserRole.Role.ADMIN)
admin_role.save()

# Per-user settings
setting = UserSetting(user=user, key="theme", value="dark")
setting.save()

# Check permissions
if user.is_admin:
    # Admin functionality
    pass
```

Your custom User model automatically inherits:
- **Authentication**: Password hashing, JWT token support
- **Relationships**: `roles`, `settings`, `tokens` 
- **Permissions**: Role-based access control with domain scoping
- **Utility methods**: `num_tokens`, `domain_ids`, `has_domain_access`

Available mixins for common extensions:
- `ProfileMixin` - Profile fields (first_name, last_name, display_name, avatar_url)
- `TimestampMixin` - Timestamp tracking (last_login_at, email_verified_at)
- `SoftDeleteMixin` - Soft delete functionality
- `OrganizationMixin` - Multi-tenant organization support

The library automatically generates filter schemas for your models:

```python
# For a User model with created_at datetime field
# Automatically supports:
GET /api/users/?created_at__from=2024-01-01&created_at__to=2024-12-31
GET /api/users/?age__min=18&age__max=65
GET /api/users/?status=active
```

## Configuration Options

### CRUDBlueprint Parameters

```python
CRUDBlueprint(
    'users',                    # Blueprint name
    __name__,                   # Import name
    model='User',               # SQLAlchemy model class name
    schema='UserSchema',        # Marshmallow schema class name
    url_prefix='/api/users/',   # URL prefix for all routes
    res_id='id',               # Primary key field name
    res_id_param='user_id',    # URL parameter name for resource ID
    skip_methods=['DELETE'],    # Skip certain CRUD operations
    methods={                   # Custom method configuration
        'GET': {'description': 'Get user details'},
        'POST': {'description': 'Create new user'}
    }
)
```

### Filtering Configuration

The query filtering automatically handles these field types:

- **DateTime/Date fields**: Converted to range filters (`__from`, `__to`)
- **Numeric fields**: Support min/max filtering (`__min`, `__max`)
- **String/Other fields**: Direct equality matching

## Examples

### Complete Flask App

```python
from flask import Flask
from flask_smorest import Api
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from flask_more_smorest import CRUDBlueprint, BaseModel
from flask_more_smorest.database import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
app.config['API_TITLE'] = 'Example API'
app.config['API_VERSION'] = 'v1'
app.config['OPENAPI_VERSION'] = '3.0.2'
app.config['SECRET_KEY'] = 'your-secret-key'

db.init_app(app)
api = Api(app)

# Define your model using BaseModel for automatic permissions
class User(BaseModel):
    username: Mapped[str] = mapped_column(db.String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True)
    
    def _can_write(self):
        """Users can only edit their own profile, admins can edit any."""
        from flask_more_smorest.user import current_user
        return self.id == current_user.id or current_user.is_admin

# Use the auto-generated schema
UserSchema = User.Schema

# Create CRUD blueprint
users_blp = CRUDBlueprint(
    'users', __name__,
    model='User',
    schema='UserSchema'
)

api.register_blueprint(users_blp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

### Custom Methods

```python
# Add custom endpoints to your CRUD blueprint
@users_blp.route('/search', methods=['POST'])
@users_blp.arguments(UserSearchSchema)
@users_blp.response(200, UserSchema(many=True))
def search_users(search_params):
    \"\"\"Advanced user search\"\"\"
    # Your custom search logic
    pass

@users_blp.route('/<int:user_id>/activate', methods=['POST'])
@users_blp.response(200, UserSchema)
@users_blp.admin_endpoint
def activate_user(user_id):
    \"\"\"Activate a user account\"\"\"
    # Your activation logic
    pass
```

## Model Features

### BaseModel

The `BaseModel` class provides a foundation for all your SQLAlchemy models with built-in:

- **Automatic timestamps**: `created_at` and `updated_at` fields
- **UUID primary keys**: Using `uuid.UUID` type for better scalability  
- **Permission system**: Built-in methods for access control (`can_read()`, `can_write()`, `can_create()`)
- **CRUD helpers**: Convenient methods like `get()`, `get_or_404()`, `save()`, `update()`, `delete()`
- **Lifecycle hooks**: `on_before_create()`, `on_after_create()`, etc.
- **Auto-generated schemas**: Dynamic Marshmallow schema generation with permission fields

### User Management Models

Ready-to-use authentication and user management:

- **User**: Core user model with email, password hashing, and role management
- **UserRole**: Role-based permissions (SUPERADMIN, ADMIN, EDITOR, USER)
- **UserSetting**: Per-user key-value settings storage
- **JWT Integration**: Built-in Flask-JWT-Extended support

### Database Integration

- **Centralized database**: Single `db` instance from `flask_more_smorest.database`
- **Modern SQLAlchemy**: Uses SQLAlchemy 2.0 patterns with `Mapped` annotations
- **Automatic schema generation**: Schemas include permission fields and relationship handling

## Requirements

- Python 3.11+
- Flask 3.0+
- Flask-Smorest
- SQLAlchemy 2.0+
- Flask-SQLAlchemy 3.1+
- Marshmallow-SQLAlchemy 1.4+
- Flask-JWT-Extended (for user authentication)
- Werkzeug (for security utilities)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and version history.