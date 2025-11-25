"""Tests demonstrating User model customization through inheritance."""

import enum
import time
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import User, UserRole, DefaultUserRole
from flask_more_smorest import db


class TestUserCustomization:
    """Test User customization through inheritance."""

    def test_basic_user_extension(self, app):
        """Test extending User with additional fields."""

        suffix = str(int(time.time() * 1000) % 100000)

        class EmployeeUser(User):
            __tablename__ = f"employee_users_{suffix}"

            employee_id: Mapped[str | None] = mapped_column(db.String(50), unique=True, nullable=True)
            department: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
            salary: Mapped[float | None] = mapped_column(db.Float, nullable=True)

            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                employee_id = kwargs.pop("employee_id", None)
                department = kwargs.pop("department", None)
                salary = kwargs.pop("salary", None)

                # Call parent constructor
                super().__init__(**kwargs)

                # Set custom fields after initialization
                self.employee_id = employee_id
                self.department = department
                self.salary = salary

            def get_benefits(self) -> list[str]:
                """Custom method for employee benefits."""
                benefits = ["health_insurance", "retirement_plan"]
                if self.salary and self.salary > 100000:
                    benefits.append("stock_options")
                return benefits

        with app.app_context():
            db.create_all()

            # Create employee
            employee = EmployeeUser(
                email=f"employee_{suffix}@company.com",
                employee_id=f"EMP{suffix}",
                department="Engineering",
                salary=120000.0,
            )
            employee.save()

            # Test custom fields
            assert employee.employee_id == f"EMP{suffix}"
            assert employee.department == "Engineering"
            assert employee.salary == 120000.0

            # Test custom method
            benefits = employee.get_benefits()
            assert "health_insurance" in benefits
            assert "stock_options" in benefits  # High salary

            # Test basic functionality
            assert employee.email == f"employee_{suffix}@company.com"
            assert employee.is_enabled is True

    def test_custom_role_enum(self, app):
        """Test creating custom role enums."""

        suffix = str(int(time.time() * 1000) % 100000)

        class CompanyRole(str, enum.Enum):
            CEO = "ceo"
            CTO = "cto"
            MANAGER = "manager"
            SENIOR_DEVELOPER = "senior_developer"
            DEVELOPER = "developer"
            INTERN = "intern"

        class CompanyUserRole(UserRole):
            __tablename__ = f"company_roles_{suffix}"
            Role = CompanyRole

        with app.app_context():
            db.create_all()

            # Create user
            user = User(email=f"dev_{suffix}@company.com")
            user.save()

            # Create role with custom enum
            with db.session.no_autoflush:
                role = CompanyUserRole(user=user, role=CompanyRole.SENIOR_DEVELOPER)
                db.session.add(role)
                db.session.commit()

            # Test role functionality
            assert role.role == CompanyRole.SENIOR_DEVELOPER
            assert role._role == "senior_developer"  # Stored as string
            assert user.has_role(CompanyRole.SENIOR_DEVELOPER)

    def test_method_overriding(self, app):
        """Test overriding User methods."""

        suffix = str(int(time.time() * 1000) % 100000)

        class VerifiedUser(User):
            __tablename__ = f"verified_users_{suffix}"

            verified: Mapped[bool | None] = mapped_column(db.Boolean, default=False, nullable=True)
            verification_date: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)

            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                verified = kwargs.pop("verified", False)
                verification_date = kwargs.pop("verification_date", None)

                # Call parent constructor
                super().__init__(**kwargs)

                # Set custom fields after initialization
                self.verified = verified
                self.verification_date = verification_date

            def _can_write(self) -> bool:
                """Override: only verified users can write."""
                return bool(self.verified) and super()._can_write()

            def verify_user(self):
                """Custom verification logic."""
                self.verified = True
                self.verification_date = datetime.now(timezone.utc)
                self.save()

        with app.app_context():
            db.create_all()

            # Create unverified user
            user = VerifiedUser(email=f"unverified_{suffix}@example.com", verified=False)
            user.save()

            # Test initial state
            assert user.verified is False
            assert user.verification_date is None

            # Verify user
            user.verify_user()

            # Test verification
            assert user.verified is True
            assert user.verification_date is not None
            assert isinstance(user.verification_date, datetime)

    def test_multiple_inheritance_with_mixins(self, app):
        """Test combining User with mixins."""

        suffix = str(int(time.time() * 1000) % 100000)

        from flask_more_smorest import ProfileMixin, SoftDeleteMixin

        class FullFeaturedUser(User, ProfileMixin, SoftDeleteMixin):
            __tablename__ = f"full_featured_users_{suffix}"

            organization: Mapped[str | None] = mapped_column(db.String(200), nullable=True)

            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                organization = kwargs.pop("organization", None)
                first_name = kwargs.pop("first_name", None)
                last_name = kwargs.pop("last_name", None)
                bio = kwargs.pop("bio", None)

                # Call parent constructor
                super().__init__(**kwargs)

                # Set custom fields after initialization
                self.organization = organization
                if hasattr(self, "first_name"):
                    self.first_name = first_name
                if hasattr(self, "last_name"):
                    self.last_name = last_name
                if hasattr(self, "bio"):
                    self.bio = bio

            @property
            def display_info(self) -> str:
                """Combine profile and custom info."""
                info = self.full_name or self.email
                if self.organization:
                    info += f" ({self.organization})"
                return info

        with app.app_context():
            db.create_all()

            # Create user with all features
            user = FullFeaturedUser(
                email=f"full_{suffix}@example.com",
                first_name="John",
                last_name="Doe",
                organization="Acme Corp",
                timezone="US/Pacific",
            )
            user.save()

            # Test ProfileMixin functionality
            assert user.full_name == "John Doe"
            assert user.first_name == "John"

            # Test custom functionality
            assert user.organization == "Acme Corp"
            assert user.display_info == "John Doe (Acme Corp)"

            # Test SoftDeleteMixin functionality
            assert not user.is_deleted
            user.soft_delete()
            assert user.is_deleted
            assert user.deleted_at is not None

    def test_backwards_compatibility(self, app):
        """Test that default User still works normally."""
        with app.app_context():
            db.create_all()

            # Create default user
            user = User(email="default@example.com")
            user.set_password("password123")
            user.save()

            # Create default role
            with db.session.no_autoflush:
                role = UserRole(user=user, role=DefaultUserRole.USER)
                db.session.add(role)
                db.session.commit()

            # Test all basic functionality works
            assert user.is_password_correct("password123")
            assert user.has_role(DefaultUserRole.USER)
            assert not user.is_admin
            assert len(user.roles) == 1
            assert user.roles[0].role == DefaultUserRole.USER


class TestRealWorldScenarios:
    """Test realistic user extension scenarios."""

    def test_multi_tenant_user_system(self, app):
        """Test user system for multi-tenant application."""

        suffix = str(int(time.time() * 1000) % 100000)

        class TenantRole(str, enum.Enum):
            SUPERADMIN = "superadmin"
            ADMIN = "admin"
            TENANT_OWNER = "tenant_owner"
            TENANT_ADMIN = "tenant_admin"
            TENANT_USER = "tenant_user"
            USER = "user"

        class TenantUserRole(UserRole):
            __tablename__ = f"tenant_roles_{suffix}"
            Role = TenantRole

        class TenantUser(User):
            __tablename__ = f"tenant_users_{suffix}"

            tenant_id: Mapped[str | None] = mapped_column(db.String(100), nullable=True)

            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                tenant_id = kwargs.pop("tenant_id", None)

                # Call parent constructor
                super().__init__(**kwargs)

                # Set custom fields after initialization
                self.tenant_id = tenant_id

            def can_access_tenant(self, tenant_id: str) -> bool:
                """Check if user can access specific tenant."""
                # Superadmin can access all tenants
                if self.has_role(TenantRole.SUPERADMIN):
                    return True
                # Users can only access their own tenant
                return self.tenant_id == tenant_id

            def get_tenant_permissions(self) -> list[str]:
                """Get permissions within user's tenant."""
                if self.has_role(TenantRole.TENANT_OWNER):
                    return ["manage_tenant", "manage_users", "view_data", "edit_data"]
                elif self.has_role(TenantRole.TENANT_ADMIN):
                    return ["manage_users", "view_data", "edit_data"]
                elif self.has_role(TenantRole.TENANT_USER):
                    return ["view_data", "edit_data"]
                return ["view_data"]

        with app.app_context():
            db.create_all()

            # Create tenant users
            owner = TenantUser(email=f"owner_{suffix}@tenant1.com", tenant_id="tenant_1", tenant_role="owner")
            owner.save()

            user = TenantUser(email=f"user_{suffix}@tenant1.com", tenant_id="tenant_1", tenant_role="user")
            user.save()

            # Assign roles
            with db.session.no_autoflush:
                owner_role = TenantUserRole(user=owner, role=TenantRole.TENANT_OWNER)
                user_role = TenantUserRole(user=user, role=TenantRole.TENANT_USER)

                db.session.add(owner_role)
                db.session.add(user_role)
                db.session.commit()

            # Test tenant access
            assert owner.can_access_tenant("tenant_1")
            assert not owner.can_access_tenant("tenant_2")
            assert user.can_access_tenant("tenant_1")
            assert not user.can_access_tenant("tenant_2")

            # Test permissions
            owner_perms = owner.get_tenant_permissions()
            user_perms = user.get_tenant_permissions()

            assert "manage_tenant" in owner_perms
            assert "manage_users" in owner_perms
            assert "manage_tenant" not in user_perms
            assert "view_data" in user_perms

    def test_api_user_with_tokens(self, app):
        """Test user extension for API usage."""

        suffix = str(int(time.time() * 1000) % 100000)

        class APIRole(str, enum.Enum):
            API_SUPERADMIN = "api_superadmin"
            API_ADMIN = "api_admin"
            API_USER = "api_user"
            READONLY = "readonly"

        class APIUserRole(UserRole):
            __tablename__ = f"api_roles_{suffix}"
            Role = APIRole

        class APIUser(User):
            __tablename__ = f"api_users_{suffix}"

            api_key: Mapped[str | None] = mapped_column(db.String(128), unique=True, nullable=True)
            last_api_call: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)
            rate_limit: Mapped[int | None] = mapped_column(db.Integer, default=1000, nullable=True)

            def __init__(self, **kwargs):
                """Initialize with custom fields."""
                # Extract custom fields before calling parent constructor
                api_key = kwargs.pop("api_key", None)
                last_api_call = kwargs.pop("last_api_call", None)

                # Call parent constructor
                super().__init__(**kwargs)

                # Set custom fields after initialization
                self.api_key = api_key
                self.last_api_call = last_api_call

            def can_make_api_call(self) -> bool:
                """Check if user can make API calls."""
                return self.api_key is not None and self.is_enabled

            def record_api_call(self):
                """Record API call timestamp."""
                self.last_api_call = datetime.now(timezone.utc)
                self.save()

            def get_api_permissions(self) -> list[str]:
                """Get API-specific permissions."""
                if self.has_role(APIRole.API_SUPERADMIN):
                    return ["read", "write", "delete", "admin"]
                elif self.has_role(APIRole.API_ADMIN):
                    return ["read", "write", "admin"]
                elif self.has_role(APIRole.API_USER):
                    return ["read", "write"]
                elif self.has_role(APIRole.READONLY):
                    return ["read"]
                return []

        with app.app_context():
            db.create_all()

            # Create API user
            api_user = APIUser(email=f"api_{suffix}@service.com", api_key=f"api_key_{suffix}", rate_limit=5000)
            api_user.save()

            # Assign API role
            with db.session.no_autoflush:
                role = APIUserRole(user=api_user, role=APIRole.API_USER)
                db.session.add(role)
                db.session.commit()

            # Test API functionality
            assert api_user.can_make_api_call()
            assert api_user.rate_limit == 5000

            # Test API call recording
            assert api_user.last_api_call is None
            api_user.record_api_call()
            assert api_user.last_api_call is not None

            # Test API permissions
            perms = api_user.get_api_permissions()
            assert "read" in perms
            assert "write" in perms
            assert "admin" not in perms
