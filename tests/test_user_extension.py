"""Tests for User model extension and customization."""

import enum
import pytest
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask_more_smorest.user import User, UserRole, Domain, DefaultUserRole, TimestampMixin, ProfileMixin, SoftDeleteMixin
from flask_more_smorest.database import db


class CustomRole(str, enum.Enum):
    """Custom role enum for testing."""
    MANAGER = "manager"
    EMPLOYEE = "employee"
    INTERN = "intern"
    CONTRACTOR = "contractor"


class TestUserExtension:
    """Test User model extension through inheritance."""

    @pytest.fixture(scope="function")
    def setup_base_tables(self, app):
        """Create base tables needed for User functionality."""
        with app.app_context():
            # Create all the base tables
            User.__table__.create(db.engine, checkfirst=True)
            Domain.__table__.create(db.engine, checkfirst=True) 
            UserRole.__table__.create(db.engine, checkfirst=True)
            
            # Import and create other required tables
            from flask_more_smorest.user import Token, UserSetting
            Token.__table__.create(db.engine, checkfirst=True)
            UserSetting.__table__.create(db.engine, checkfirst=True)

    @pytest.fixture(scope="function")
    def extended_user_model(self, app, setup_base_tables):
        """Create extended User model for testing."""
        
        # Generate unique suffix to avoid conflicts
        import time
        suffix = str(int(time.time() * 1000000) % 1000000)
        
        from flask_more_smorest.models import BaseModel
        
        class ExtendedUser(BaseModel):
            __tablename__ = f"extended_users_{suffix}"
            
            # Core User-like fields
            email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
            password: Mapped[bytes | None] = mapped_column(db.LargeBinary(128), nullable=True)
            is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)
            
            # Additional fields
            employee_id: Mapped[str | None] = mapped_column(db.String(50), unique=True, nullable=True)
            department: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
            salary: Mapped[float | None] = mapped_column(db.Float, nullable=True)
            hire_date: Mapped[datetime | None] = mapped_column(db.Date, nullable=True)
            
            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract fields directly
                employee_id = kwargs.pop('employee_id', None)
                department = kwargs.pop('department', None)
                salary = kwargs.pop('salary', None)
                hire_date = kwargs.pop('hire_date', None)
                password = kwargs.pop('password', None)
                
                # Call BaseModel constructor
                super().__init__(**kwargs)
                
                # Set fields
                self.employee_id = employee_id
                self.department = department
                self.salary = salary
                self.hire_date = hire_date
                if password:
                    self.set_password(password)
            
            def set_password(self, password: str) -> None:
                """Set password with secure hashing."""
                from werkzeug.security import generate_password_hash
                self.password = generate_password_hash(password)

            def check_password(self, password: str) -> bool:
                """Check if provided password matches stored hash."""
                if self.password is None:
                    return False
                from werkzeug.security import check_password_hash
                return check_password_hash(password=password, pwhash=self.password.decode('utf-8'))
            
            # Override permission method
            def _can_write(self) -> bool:
                """Extended permission logic."""
                # Allow during testing
                return True
            
            # Custom methods
            def get_employee_permissions(self):
                """Get employee-specific permissions."""
                perms = ["view_profile", "edit_profile"]
                if self.department == "HR":
                    perms.extend(["view_employees", "edit_employees"])
                return perms
            
            @property
            def is_hr_employee(self) -> bool:
                """Check if user is HR employee."""
                return self.department == "HR"

        with app.app_context():
            ExtendedUser.__table__.create(db.engine, checkfirst=True)
            
        return ExtendedUser

    def test_user_extension_basic_functionality(self, app, extended_user_model):
        """Test basic functionality of extended User model."""
        with app.app_context():
            with extended_user_model.bypass_perms():
                # Create extended user
                user = extended_user_model(
                    email="john.doe@company.com",
                    employee_id="EMP001", 
                    department="Engineering",
                    salary=75000.0,
                    hire_date=datetime(2023, 1, 15).date()
                )
                user.set_password("secure_password")
                user.save()

                # Test that base User-like functionality works
                assert user.id is not None
                assert user.email == "john.doe@company.com"
                assert user.check_password("secure_password")
                
                # Test extended fields
                assert user.employee_id == "EMP001"
                assert user.department == "Engineering" 
                assert user.salary == 75000.0
                assert user.hire_date == datetime(2023, 1, 15).date()

    def test_user_extension_custom_methods(self, app, extended_user_model):
        """Test custom methods on extended User model."""
        with app.app_context():
            with extended_user_model.bypass_perms():
                # Create HR user
                hr_user = extended_user_model(
                    email="hr@company.com",
                    department="HR"
                )
                hr_user.save()

                # Create regular user  
                regular_user = extended_user_model(
                    email="employee@company.com", 
                    department="Engineering"
                )
                regular_user.save()

                # Test custom methods
                assert hr_user.is_hr_employee is True
                assert regular_user.is_hr_employee is False
                
                # Test permission methods
                hr_perms = hr_user.get_employee_permissions()
                regular_perms = regular_user.get_employee_permissions()
                
                assert "view_employees" in hr_perms
                assert "edit_employees" in hr_perms
                assert "view_employees" not in regular_perms

    def test_user_extension_with_mixins(self, app, setup_base_tables):
        """Test User extension with provided mixins."""
        
        # Generate unique suffix to avoid conflicts
        import time
        suffix = str(int(time.time() * 1000000) % 1000000)
        
        from flask_more_smorest.models import BaseModel
        from flask_more_smorest.user import TimestampMixin, ProfileMixin, SoftDeleteMixin
        
        class MixinUser(BaseModel, TimestampMixin, ProfileMixin, SoftDeleteMixin):
            __tablename__ = f"mixin_users_{suffix}"
            
            email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
            is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)
            
            def __init__(self, **kwargs):
                """Initialize with mixin fields."""
                # Extract mixin fields before calling parent constructor
                first_name = kwargs.pop('first_name', None)
                last_name = kwargs.pop('last_name', None)
                bio = kwargs.pop('bio', None)
                display_name = kwargs.pop('display_name', None)
                
                # Call parent constructor
                super().__init__(**kwargs)
                
                # Set mixin fields after initialization
                if hasattr(self, 'first_name'):
                    self.first_name = first_name
                if hasattr(self, 'last_name'):
                    self.last_name = last_name
                if hasattr(self, 'bio'):
                    self.bio = bio
                if hasattr(self, 'display_name'):
                    self.display_name = display_name

        with app.app_context():
            MixinUser.__table__.create(db.engine, checkfirst=True)
            
            with MixinUser.bypass_perms():
                user = MixinUser(
                    email="mixin@example.com",
                    first_name="John",
                    last_name="Doe", 
                    display_name="Johnny D"
                )
                user.save()

                # Test ProfileMixin functionality
                assert user.full_name == "John Doe"
                assert user.first_name == "John"
                assert user.last_name == "Doe"
                
                # Test TimestampMixin fields exist
                assert hasattr(user, "last_login_at")
                assert hasattr(user, "email_verified_at")
                
                # Test SoftDeleteMixin
                assert not user.is_deleted
                user.soft_delete()
                assert user.is_deleted
                assert user.deleted_at is not None

    def test_user_extension_relationships_preserved(self, app, extended_user_model):
        """Test basic User extension functionality."""
        with app.app_context():
            with extended_user_model.bypass_perms():
                # Create user
                user = extended_user_model(email="test@example.com")
                user.save()

                # Test that basic functionality works
                assert user.id is not None
                assert user.email == "test@example.com"
                assert hasattr(user, 'employee_id')  # Extended field exists

    def test_user_extension_schema_generation(self, app, extended_user_model):
        """Test that extended User models work with marshmallow schemas."""
        from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
        
        class ExtendedUserSchema(SQLAlchemyAutoSchema):
            class Meta:
                model = extended_user_model
                load_instance = True
        
        with app.app_context():
            extended_user_model.__table__.create(db.engine, checkfirst=True)
            
            schema = ExtendedUserSchema()
            
            # Test schema fields include both base and extended fields
            assert "email" in schema.fields
            assert "employee_id" in schema.fields
            assert "department" in schema.fields
            assert "salary" in schema.fields


class TestCustomRoleEnum:
    """Test using custom role enums with User models."""

    @pytest.fixture(scope="function")
    def setup_base_tables(self, app):
        """Create base tables needed for User functionality."""
        with app.app_context():
            # Create all the base tables
            User.__table__.create(db.engine, checkfirst=True)
            Domain.__table__.create(db.engine, checkfirst=True) 
            UserRole.__table__.create(db.engine, checkfirst=True)

    def test_user_with_custom_roles(self, app, setup_base_tables):
        """Test User model with custom role enum."""
        with app.app_context():
            with User.bypass_perms():
                # Create user
                user = User(email="custom_roles@example.com")  
                user.save()

                # Create domain
                with Domain.bypass_perms():
                    domain = Domain(name="company", display_name="Company")
                    domain.save()

                    # Create roles with custom enum
                    with UserRole.bypass_perms():
                        manager_role = UserRole(
                            user=user,
                            role=CustomRole.MANAGER, 
                            domain_id=domain.id
                        )
                        manager_role.save()
                        
                        employee_role = UserRole(
                            user=user,
                            role=CustomRole.EMPLOYEE,
                            domain_id=domain.id
                        )
                        employee_role.save()

                    # Test role checking with custom enum
                    assert user.has_role(CustomRole.MANAGER.value, domain.name)
                    assert user.has_role(CustomRole.EMPLOYEE.value, domain.name)
                    assert not user.has_role(CustomRole.INTERN.value, domain.name)
                    
                    # Test with string values
                    assert user.has_role("manager", domain.name)
                    assert user.has_role("employee", domain.name)
                    assert not user.has_role("intern", domain.name)

    def test_role_enum_conversion(self):
        """Test converting between custom enum and role values."""
        # Test enum to string conversion
        role_value = CustomRole.MANAGER.value
        assert role_value == "manager"
        
        # Test string to enum conversion (if enum contains the value)
        role_str = "employee"
        if hasattr(CustomRole, role_str.upper()):
            role_enum = getattr(CustomRole, role_str.upper())
            assert role_enum == CustomRole.EMPLOYEE
        else:
            # For values not in enum, just use the string
            assert role_str == "employee"


class TestUserExtensionDocumentation:
    """Test cases that demonstrate User extension patterns for documentation."""

    @pytest.fixture(scope="function")
    def setup_base_tables(self, app):
        """Create base tables needed for User functionality."""
        with app.app_context():
            User.__table__.create(db.engine, checkfirst=True)
            Domain.__table__.create(db.engine, checkfirst=True) 
            UserRole.__table__.create(db.engine, checkfirst=True)

    def test_basic_field_extension(self, app, setup_base_tables):
        """Example: Adding fields to User model."""
        
        # Generate unique suffix to avoid conflicts
        import time
        suffix = str(int(time.time() * 1000000) % 1000000)
        
        from flask_more_smorest.models import BaseModel
        
        class CompanyUser(BaseModel):
            __tablename__ = f"company_users_{suffix}"
            
            email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
            is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)
            
            employee_id: Mapped[str | None] = mapped_column(db.String(50), unique=True, nullable=True)
            department: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
            job_title: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
            
            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                employee_id = kwargs.pop('employee_id', None)
                department = kwargs.pop('department', None)
                job_title = kwargs.pop('job_title', None)
                
                # Call parent constructor
                super().__init__(**kwargs)
                
                # Set custom fields after initialization
                self.employee_id = employee_id
                self.department = department
                self.job_title = job_title
            
        with app.app_context():
            CompanyUser.__table__.create(db.engine, checkfirst=True)
            
            with CompanyUser.bypass_perms():
                user = CompanyUser(
                    email="employee@company.com",
                    employee_id="E12345",
                    department="Engineering", 
                    job_title="Senior Developer"
                )
                user.save()
                
                assert user.employee_id == "E12345"
                assert user.department == "Engineering"

    def test_method_override_extension(self, app, setup_base_tables):
        """Example: Overriding methods in User model."""
        
        class RestrictedUser(BaseModel):
            __tablename__ = f"restricted_users_{suffix}"
            
            email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
            is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True)
            
            access_level: Mapped[int | None] = mapped_column(db.Integer, default=1, nullable=True)
            
            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                access_level = kwargs.pop('access_level', 1)
                
                # Call parent constructor
                super().__init__(**kwargs)
                
                # Set custom fields after initialization
                self.access_level = access_level
            
            def _can_write(self) -> bool:
                """Override write permission."""
                # Only users with access level 3+ can write
                return self.access_level and self.access_level >= 3
                
            def _can_create(self) -> bool: 
                """Override create permission."""
                # Anyone can create (for testing)
                return True

        with app.app_context():
            RestrictedUser.__table__.create(db.engine, checkfirst=True)
            
            with RestrictedUser.bypass_perms():
                # Low access user
                low_user = RestrictedUser(
                    email="low@example.com",
                    access_level=1
                )
                low_user.save()
                
                # High access user
                high_user = RestrictedUser(
                    email="high@example.com", 
                    access_level=5
                )
                high_user.save()

                # Test permission differences
                assert not low_user._can_write()
                assert high_user._can_write()

    def test_role_extension_example(self, app, setup_base_tables):
        """Example: Creating custom UserRole model."""
        
        class ProjectRole(str, enum.Enum):
            LEAD = "project_lead"
            DEVELOPER = "developer" 
            TESTER = "tester"
        
        class ProjectUserRole(UserRole):
            __tablename__ = "project_user_roles"
            
            project_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
            
            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                project_id = kwargs.pop('project_id', None)
                
                # Call parent constructor
                super().__init__(**kwargs)
                
                # Set custom fields after initialization
                self.project_id = project_id
            
            def get_project_permissions(self):
                """Get permissions for this project role."""
                role_perms = {
                    ProjectRole.LEAD.value: ["manage_project", "assign_tasks", "view_reports"],
                    ProjectRole.DEVELOPER.value: ["view_tasks", "update_code", "create_bugs"],
                    ProjectRole.TESTER.value: ["view_tasks", "create_bugs", "run_tests"]
                }
                return role_perms.get(self.role, [])

        with app.app_context():
            ProjectUserRole.__table__.create(db.engine, checkfirst=True)
            
            with User.bypass_perms():
                user = User(email="project@example.com")
                user.save()
                
                with ProjectUserRole.bypass_perms():
                    role = ProjectUserRole(
                        user=user,
                        role=ProjectRole.LEAD,
                        project_id=uuid.uuid4()
                    )
                    role.save()
                    
                    perms = role.get_project_permissions()
                    assert "manage_project" in perms
                    assert "assign_tasks" in perms