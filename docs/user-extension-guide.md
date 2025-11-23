# User Model Extension Guide

This guide provides detailed patterns for extending the Flask-More-Smorest User model to meet your application's specific requirements.

## Overview

The User model in Flask-More-Smorest is designed for easy extension while preserving all core authentication and permission functionality. You can:

- Add custom fields to store additional user data
- Override methods to implement custom business logic
- Use provided mixins for common functionality
- Maintain all built-in features (roles, settings, tokens, permissions)

## Basic Extension Pattern

### Simple Field Addition

```python
from flask_more_smorest import User
from flask_more_smorest.database import db
from sqlalchemy.orm import Mapped, mapped_column

class CustomUser(User):
    """Extended User model with additional fields."""
    
    # Custom fields
    bio: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    department: Mapped[str] = mapped_column(db.String(100), default="Engineering") 
    security_clearance: Mapped[int] = mapped_column(db.Integer, default=1)
    
    # Override methods if needed
    def _can_write(self) -> bool:
        """Only users with sufficient clearance can edit profiles."""
        return self.security_clearance >= 3 and super()._can_write()
    
    @property
    def display_info(self) -> str:
        """Custom property for display."""
        return f"{self.email} ({self.department})"
```

### Method Override Examples

```python
class RestrictedUser(User):
    """User with additional validation and restrictions."""
    
    email_verified: Mapped[bool] = mapped_column(db.Boolean, default=False)
    login_attempts: Mapped[int] = mapped_column(db.Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)
    
    def update(self, commit: bool = True, force: bool = False, **kwargs) -> "RestrictedUser":
        """Override to add email verification requirement."""
        # Require verification for sensitive changes
        if any(field in kwargs for field in ['email', 'password']):
            if not self.email_verified and not force:
                raise UnprocessableEntity(
                    message="Email verification required for sensitive changes"
                )
        
        return super().update(commit=commit, force=force, **kwargs)
    
    def set_password(self, password: str) -> None:
        """Override to add password complexity validation."""
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain uppercase letters")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain numbers")
            
        super().set_password(password)
    
    @property
    def is_locked(self) -> bool:
        """Check if account is temporarily locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    def unlock_account(self) -> None:
        """Unlock account and reset login attempts."""
        self.locked_until = None
        self.login_attempts = 0
        self.save()
```

## Using Mixins

Flask-More-Smorest provides several mixins for common functionality:

### ProfileMixin - User Profile Fields

```python
from flask_more_smorest.user import ProfileMixin

class ProfileUser(User, ProfileMixin):
    """User with profile information."""
    
    # Inherits: first_name, last_name, display_name, avatar_url
    # Plus: full_name property
    
    job_title: Mapped[str | None] = mapped_column(db.String(100))
    phone: Mapped[str | None] = mapped_column(db.String(20))
    
    @property 
    def professional_name(self) -> str:
        """Get professional display name."""
        if self.job_title and self.full_name:
            return f"{self.full_name}, {self.job_title}"
        return self.full_name or self.display_name or self.email
```

### TimestampMixin - Additional Timestamps

```python
from flask_more_smorest.user import TimestampMixin

class TimestampUser(User, TimestampMixin):
    """User with additional timestamp tracking."""
    
    # Inherits: last_login_at, email_verified_at
    
    def record_login(self) -> None:
        """Record successful login."""
        self.last_login_at = datetime.now(timezone.utc)
        self.save()
    
    def verify_email(self) -> None:
        """Mark email as verified."""
        self.email_verified_at = datetime.now(timezone.utc)
        self.save()
    
    @property
    def is_email_verified(self) -> bool:
        """Check if email is verified."""
        return self.email_verified_at is not None
```

### SoftDeleteMixin - Soft Delete Support

```python
from flask_more_smorest.user import SoftDeleteMixin

class SoftDeleteUser(User, SoftDeleteMixin):
    """User with soft delete functionality."""
    
    # Inherits: deleted_at, is_deleted property, soft_delete(), restore()
    
    def delete_with_reason(self, reason: str) -> None:
        """Soft delete with audit trail."""
        self.deletion_reason = reason
        self.soft_delete()
        self.save()
    
    @classmethod
    def active_users(cls):
        """Query helper for non-deleted users."""
        return cls.query.filter(cls.deleted_at.is_(None))
```

### Combining Multiple Mixins

```python
class FullUser(User, ProfileMixin, TimestampMixin, SoftDeleteMixin):
    """User with all common extensions."""
    
    # Additional custom fields
    api_access_level: Mapped[int] = mapped_column(db.Integer, default=1)
    notifications_enabled: Mapped[bool] = mapped_column(db.Boolean, default=True)
    
    @property
    def is_premium(self) -> bool:
        """Check if user has premium access."""
        return self.api_access_level >= 5
    
    @property
    def is_admin(self) -> bool:
        """Override admin check to include API access level."""
        return self.api_access_level >= 8 or super().is_admin
```

## Real-World Examples

### Multi-Tenant SaaS Application

```python
class TenantUser(User, ProfileMixin):
    """User in a multi-tenant SaaS application."""
    
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    subscription_tier: Mapped[str] = mapped_column(db.String(20), default="basic")
    feature_flags: Mapped[dict] = mapped_column(db.JSON, default=dict)
    
    @declared_attr
    def tenant(cls) -> Mapped["Tenant"]:
        return relationship("Tenant", back_populates="users")
    
    def has_feature(self, feature_name: str) -> bool:
        """Check if user has access to a feature."""
        return self.feature_flags.get(feature_name, False)
    
    def _can_read(self) -> bool:
        """Users can only read within their tenant."""
        try:
            current = get_current_user()
            return current.tenant_id == self.tenant_id or current.is_admin
        except:
            return False
```

### E-commerce Application

```python
class CustomerUser(User, ProfileMixin, TimestampMixin):
    """Customer user for e-commerce platform."""
    
    customer_type: Mapped[str] = mapped_column(db.String(20), default="retail") 
    loyalty_points: Mapped[int] = mapped_column(db.Integer, default=0)
    preferred_currency: Mapped[str] = mapped_column(db.String(3), default="USD")
    marketing_consent: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    @declared_attr
    def orders(cls) -> Mapped[list["Order"]]:
        return relationship("Order", back_populates="customer")
        
    @declared_attr 
    def addresses(cls) -> Mapped[list["Address"]]:
        return relationship("Address", back_populates="user", cascade="all, delete-orphan")
    
    @property
    def lifetime_value(self) -> Decimal:
        """Calculate customer lifetime value."""
        return sum(order.total for order in self.orders)
    
    @property
    def loyalty_tier(self) -> str:
        """Determine loyalty tier based on points."""
        if self.loyalty_points >= 10000:
            return "platinum"
        elif self.loyalty_points >= 5000:
            return "gold" 
        elif self.loyalty_points >= 1000:
            return "silver"
        return "bronze"
    
    def add_loyalty_points(self, points: int, description: str = "") -> None:
        """Add loyalty points with audit trail."""
        self.loyalty_points += points
        # Could also create a LoyaltyTransaction record here
        self.save()
```

### Enterprise Application

```python
class EmployeeUser(User, ProfileMixin, TimestampMixin):
    """Employee user for enterprise application."""
    
    employee_id: Mapped[str] = mapped_column(db.String(20), unique=True)
    hire_date: Mapped[date] = mapped_column(db.Date, nullable=False)
    position: Mapped[str] = mapped_column(db.String(100))
    cost_center: Mapped[str] = mapped_column(db.String(20))
    manager_id: Mapped[UUID | None] = mapped_column(sa.Uuid, db.ForeignKey('users.id'))
    
    @declared_attr
    def manager(cls) -> Mapped["EmployeeUser | None"]:
        return relationship("EmployeeUser", remote_side=cls.id, back_populates="direct_reports")
    
    @declared_attr
    def direct_reports(cls) -> Mapped[list["EmployeeUser"]]:
        return relationship("EmployeeUser", back_populates="manager")
    
    @property
    def is_manager(self) -> bool:
        """Check if user manages other employees."""
        return len(self.direct_reports) > 0
    
    @property
    def years_of_service(self) -> int:
        """Calculate years of service."""
        return (date.today() - self.hire_date).days // 365
    
    def _can_read(self) -> bool:
        """Employees can read their own data and their direct reports'."""
        try:
            current = get_current_user()
            if current.id == self.id:
                return True
            if current.is_admin:
                return True
            return self in current.direct_reports
        except:
            return False
    
    def transfer_to_manager(self, new_manager: "EmployeeUser") -> None:
        """Transfer employee to new manager."""
        old_manager = self.manager
        self.manager = new_manager
        self.save()
        
        # Could trigger notifications, workflow, etc.
        self._notify_transfer(old_manager, new_manager)
```

## Important Notes

### Table Inheritance Patterns

When extending the User model, you have several options for table structure:

1. **Single Table Inheritance (default)** - Add fields to existing `users` table
2. **Joined Table Inheritance** - Create separate table for extended fields
3. **Separate Table** - Create completely separate table with foreign key

```python
# Single table inheritance (adds columns to users table)
class ExtendedUser(User):
    extra_field: Mapped[str] = mapped_column(db.String(100))

# Joined table inheritance (separate table joined to users) 
class ExtendedUser(User):
    __tablename__ = 'extended_users'
    id: Mapped[UUID] = mapped_column(sa.Uuid, db.ForeignKey('users.id'), primary_key=True)
    extra_field: Mapped[str] = mapped_column(db.String(100))

# Separate table (no inheritance)
class UserProfile(BaseModel):
    __tablename__ = 'user_profiles'
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, db.ForeignKey('users.id'))
    user: Mapped[User] = relationship('User')
    extra_field: Mapped[str] = mapped_column(db.String(100))
```

### Preserving Core Functionality

When extending the User model, always:

- Call `super()` in overridden methods to preserve base functionality
- Test that relationships (roles, settings, tokens) still work
- Verify permission methods still function correctly 
- Ensure JWT authentication integration remains intact

### Testing Your Extensions

```python
def test_custom_user_functionality():
    """Test extended User model."""
    user = CustomUser(
        email="test@example.com",
        password="secret123",
        bio="Test user bio",
        department="Engineering"
    )
    user.save()
    
    # Test base functionality still works
    assert user.is_password_correct("secret123")
    assert not user.is_admin
    
    # Test custom functionality
    assert user.bio == "Test user bio"
    assert user.department == "Engineering"
    assert "Engineering" in user.display_info
    
    # Test relationships still work
    role = UserRole(user=user, role=UserRole.Role.EDITOR)
    role.save()
    
    assert user.has_role(UserRole.Role.EDITOR)
    assert len(user.roles) == 1
```
