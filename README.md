# Flask-More-Smorest

[![PyPI version](https://badge.fury.io/py/flask-more-smorest.svg)](https://badge.fury.io/py/flask-more-smorest)
[![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg)](https://pypi.org/project/flask-more-smorest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A powerful extension library for Flask-Smorest that provides automatic CRUD operations, permission-based access, and out-of-the-box models for user management.

## Features

- 🚀 **Automatic CRUD Operations**: Generate complete RESTful APIs with minimal code
- 📝 **Enhanced Blueprints**: Additional decorators for public/admin endpoints  
- 🔍 **Advanced Query Filtering**: Automatic filtering with range queries for dates
- 🏷️ **Operation ID Generation**: Automatic OpenAPI operationId generation
- 🔐 **Permission-Based Models**: BaseModel with built-in permission checking and user context
- 👤 **User Management**: Complete User/UserRole models with authentication and customization
- 🛡️ **Security Features**: JWT integration, password hashing, role-based access control
- 📊 **Auto-Generated Schemas**: Dynamic Marshmallow schemas with permission fields

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

Flask-More-Smorest provides a comprehensive user management system that supports simple customization through inheritance. The system is designed to be flexible while maintaining all the core functionality you need.

#### Using the Default User Model

The built-in `User` model provides everything needed for most applications:

```python
from flask_more_smorest.user import User, UserRole, UserSetting, DefaultUserRole

# Use the default User model as-is
user = User(email="user@example.com")
user.set_password("secure_password") 
user.save()

# Built-in role management with default roles
admin_role = UserRole(user=user, role=DefaultUserRole.ADMIN)
admin_role.save()

# Per-user settings
setting = UserSetting(user=user, key="theme", value="dark")
setting.save()

# Check permissions
if user.is_admin:
    # Admin functionality
    pass
```

#### Extending the User Model

The recommended pattern is to extend the default `User` class through simple inheritance:

```python
from flask_more_smorest.user import User, ProfileMixin, TimestampMixin
from flask_more_smorest.database import db
from sqlalchemy.orm import Mapped, mapped_column

# Simple extension with custom fields and mixins
class EmployeeUser(User, ProfileMixin, TimestampMixin):
    """Employee user with company-specific fields and logic."""
    __tablename__ = "employee_users"  # Use separate table
    
    # Add custom fields
    employee_id: Mapped[str] = mapped_column(db.String(50), unique=True)
    department: Mapped[str] = mapped_column(db.String(100))
    job_title: Mapped[str] = mapped_column(db.String(100))
    
    # Add custom methods
    def get_employee_permissions(self) -> list[str]:
        """Custom method for employee-specific permissions."""
        base_perms = ["view_profile", "edit_profile"]
        if self.department == "HR":
            base_perms.extend(["manage_users", "view_reports"])
        return base_perms
    
    # Override permission methods if needed
    def _can_write(self) -> bool:
        """Custom permission logic."""
        return self.department == "Engineering" and super()._can_write()

    @property
    def is_employee(self) -> bool:
        return self.employee_id is not None
```

#### Using Custom Role Enums

You can use custom role enums with the existing UserRole model:

```python
import enum
from flask_more_smorest.user import UserRole

class CompanyRole(str, enum.Enum):
    CEO = "ceo"
    MANAGER = "manager" 
    EMPLOYEE = "employee"
    INTERN = "intern"

# Create roles with custom enum values
role = UserRole(user=user, role=CompanyRole.MANAGER)
role.save()

# Check roles with enum or string values
if user.has_role(CompanyRole.MANAGER):
    # Manager functionality
    pass

if user.has_role("manager"):  # Also works with strings
    # Same functionality
    pass
```

#### Extending UserRole Model

For more complex role management, extend UserRole as well:

```python
class ProjectUserRole(UserRole):
    """Project-specific role with additional metadata.""" 
    __tablename__ = "project_user_roles"
    
    project_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(db.DateTime, nullable=True)
    
    def is_expired(self) -> bool:
        """Check if role assignment is expired."""
        return self.expires_at and datetime.utcnow() > self.expires_at
```

# Use provided mixins for common functionality
class EnhancedUser(User, ProfileMixin, TimestampMixin):
    """User with profile fields and additional timestamps."""
    
    # Inherits first_name, last_name, display_name, avatar_url from ProfileMixin
    # Inherits last_login_at, email_verified_at from TimestampMixin
    security_level: Mapped[int] = mapped_column(db.Integer, default=1)
    
    @property
    def is_admin(self) -> bool:
        """Admin if high security level or has admin role."""
        return self.security_level >= 8 or super().is_admin
```

Your custom User model automatically inherits:
- **Authentication**: Password hashing, JWT token support
- **Relationships**: `roles`, `settings`, `tokens` collections
- **Permissions**: Role-based access control with domain scoping  
- **Utility methods**: `num_tokens`, `domain_ids`, `has_domain_access`
- **Core methods**: `has_role()`, `is_admin`, `is_superadmin`

#### Available Mixins

Use these mixins to add common functionality without reimplementing:

```python
from flask_more_smorest.user import ProfileMixin, TimestampMixin, SoftDeleteMixin

# ProfileMixin - Basic profile fields
class ProfileUser(User, ProfileMixin):
    # Adds: first_name, last_name, display_name, avatar_url
    # Provides: full_name property
    pass

# TimestampMixin - Additional timestamp tracking  
class TimestampUser(User, TimestampMixin):
    # Adds: last_login_at, email_verified_at
    pass

# SoftDeleteMixin - Soft delete functionality
class SoftDeleteUser(User, SoftDeleteMixin):
    # Adds: deleted_at, is_deleted property
    # Provides: soft_delete(), restore() methods
    pass

# Combine multiple mixins for rich user models
class FullUser(User, ProfileMixin, TimestampMixin, SoftDeleteMixin):
    """User with comprehensive functionality."""
    __mapper_args__ = {"polymorphic_identity": "full"}
    
    # Built-in fields are automatically available
    # api_key, organization, timezone, etc.
```

#### Custom Role Systems

Flask-More-Smorest supports custom role enums through a simple composition pattern:

```python
import enum
from flask_more_smorest import UserRole, User

# Define custom roles for your domain
class CompanyRole(str, enum.Enum):
    SUPERADMIN = "superadmin"  # Include base roles
    ADMIN = "admin"           
    MANAGER = "manager"        # Add custom roles
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    USER = "user"

# Optional: Create helper class for convenience
class CompanyUserRole(UserRole):
    """Helper for company role operations."""
    
    @property
    def company_role(self) -> CompanyRole:
        """Get role as CompanyRole enum."""
        return CompanyRole(self.role)

# Usage
user = User(email="employee@company.com")
role = UserRole(user=user, role=CompanyRole.EMPLOYEE)
# or with helper:
role = CompanyUserRole(user=user, role=CompanyRole.EMPLOYEE)

# Role checking works with any enum
assert user.has_role(CompanyRole.EMPLOYEE)
assert role.company_role == CompanyRole.EMPLOYEE
```

**Simple Inheritance**: The User model uses single-table inheritance with polymorphic identities. Just specify `__mapper_args__ = {"polymorphic_identity": "your_type"}` when extending.

**Built-in Extension Fields**: Common fields like `employee_id`, `department`, `organization`, `verified`, `api_key`, etc. are already available - no need to redeclare them.

The role system maintains backward compatibility - existing applications using the default roles will continue working without changes.

#### Advanced Customization

Override methods to customize behavior:

```python
class RestrictedUser(User):
    verification_required: Mapped[bool] = mapped_column(db.Boolean, default=True)
    
    def update(self, commit: bool = True, force: bool = False, **kwargs) -> "RestrictedUser":
        """Override update to require verification for sensitive changes."""
        if 'password' in kwargs and self.verification_required:
            if not kwargs.pop('verified', False):
                raise UnprocessableEntity(
                    message="Email verification required for password changes"
                )
        
        return super().update(commit=commit, force=force, **kwargs)
    
    def _can_write(self) -> bool:
        """Only verified users can modify their profiles."""
        return not self.verification_required and super()._can_write()
```

#### Multi-Tenant Support

The user system includes built-in multi-tenant support:

```python
from flask_more_smorest.user import Domain

# Create domains for different tenants
domain1 = Domain(name="company-a", display_name="Company A")
domain2 = Domain(name="company-b", display_name="Company B")

# Assign roles scoped to specific domains
role1 = UserRole(user=user, role=UserRole.Role.ADMIN, domain=domain1)
role2 = UserRole(user=user, role=UserRole.Role.USER, domain=domain2)

# Check domain-specific permissions
if user.has_role(UserRole.Role.ADMIN, "company-a"):
    # User is admin in Company A
    pass

if user.has_domain_access(domain1.id):
    # User has access to Company A
    pass
```

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
- **UserRole**: Role-based permissions (SUPERADMIN, ADMIN, USER) - easily extensible
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