"""Integration tests for User model extension with permissions checking.

This test demonstrates:
- Creating a CustomUserModel class that extends the package's User class
- Testing user-related default tables (settings, tokens, roles)
- Testing a model with UserOwnershipMixin for permission access
- Testing a model with custom permission rules
"""

from __future__ import annotations

import sys
import types
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask_more_smorest import db, init_db, init_jwt
from flask_more_smorest.error.exceptions import ForbiddenError
from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.base_perms_model import BasePermsModel
from flask_more_smorest.perms.model_mixins import ProfileMixin, UserOwnershipMixin
from flask_more_smorest.perms.models.abstract_user import AbstractUser
from flask_more_smorest.perms.models.base_roles import BaseRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.orm import scoped_session


@pytest.fixture(scope="module", autouse=True)
def _module_cleanup() -> Iterator[None]:
    yield
    clear_registration()
    db.metadata.clear()


@pytest.fixture(scope="module", autouse=True)
def custom_models() -> Iterator[SimpleNamespace]:
    """Create custom user model and related models in a dynamic module."""
    clear_registration()
    db.metadata.clear()
    module_name = f"{__name__}.dynamic_{uuid.uuid4().hex}"

    module = types.ModuleType(module_name)
    module.__dict__.update(globals())
    sys.modules[module_name] = module

    from flask_more_smorest.perms.models.abstract_role import AbstractDomain, AbstractUserRole
    from flask_more_smorest.perms.models.abstract_setting import AbstractUserSetting
    from flask_more_smorest.perms.models.abstract_token import AbstractToken

    class CustomUserModel(ProfileMixin, AbstractUser):  # type: ignore[misc,valid-type]
        """Custom User class that extends the base User class.

        Adds additional fields specific to this application:
        - bio: User biography
        - phone_number: Contact phone number
        - is_verified: Whether the user has been verified
        """

        __tablename__ = "user"
        __module__ = module_name

        bio: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
        phone_number: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
        is_verified: Mapped[bool] = mapped_column(sa.Boolean(), default=False)

        def _can_write(self, current_user: AbstractUser | None) -> bool:
            """Override write permission to require verification.

            Only verified users can edit their own profiles.
            Admins can edit any profile regardless of verification.

            Args:
                current_user: The current authenticated user, or None
            """
            from flask_more_smorest.perms.user_context import is_current_user_admin

            # Allow admins to write
            if is_current_user_admin():
                return True

            # Check if user is editing their own profile
            if not current_user or current_user.id != self.id:
                return False

            # Require verification for self-edit
            return self.is_verified  # type: ignore[attr-defined]

    class CustomDomain(AbstractDomain):
        """Default domain implementation."""

        __module__ = module_name

    class CustomUserRole(AbstractUserRole):
        """Default user role implementation."""

        __module__ = module_name

    class CustomToken(AbstractToken):
        """Default token implementation."""

        __module__ = module_name

    class CustomUserSetting(AbstractUserSetting):
        """Default user setting implementation."""

        __module__ = module_name

    class Note(UserOwnershipMixin, BasePermsModel):
        """Note model with UserOwnershipMixin.

        This model demonstrates user-owned resources where:
        - Users can only read their own notes
        - Users can only write their own notes
        """

        __tablename__ = "note"
        __module__ = module_name

        title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
        content: Mapped[str] = mapped_column(sa.Text, nullable=False)

    class Document(BasePermsModel):
        """Document model with custom permission rules.

        This model demonstrates custom permission logic where:
        - Public documents can be read by anyone
        - Private documents can only be read by the owner
        - Only the owner can write documents
        - Only verified users can create documents
        """

        __tablename__ = "document"
        __module__ = module_name

        title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
        content: Mapped[str] = mapped_column(sa.Text, nullable=False)
        is_public: Mapped[bool] = mapped_column(sa.Boolean(), default=False)
        owner_id: Mapped[uuid.UUID] = mapped_column(
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("user.id"),
            nullable=False,
        )

        owner: Mapped[CustomUserModel] = relationship(CustomUserModel)  # type: ignore[valid-type]

        def _can_read(self, current_user: AbstractUser | None) -> bool:
            """Custom read permission: public docs readable by all, private only by owner."""
            if self.is_public:
                return True

            return current_user is not None and current_user.id == self.owner_id

        def _can_write(self, current_user: AbstractUser | None) -> bool:
            """Custom write permission: only owner can write."""
            return current_user is not None and current_user.id == self.owner_id

        def _can_create(self, current_user: AbstractUser | None) -> bool:
            """Custom create permission: only verified users can create documents."""
            if not current_user:
                return False

            owner = db.session.get(CustomUserModel, current_user.id)
            return owner.is_verified if owner else False  # type: ignore[attr-defined]

    models = SimpleNamespace(
        CustomUserModel=CustomUserModel,
        CustomDomain=CustomDomain,
        CustomUserRole=CustomUserRole,
        CustomToken=CustomToken,
        CustomUserSetting=CustomUserSetting,
        Note=Note,
        Document=Document,
    )

    try:
        yield models
    finally:
        sys.modules.pop(module_name, None)
        clear_registration()


@pytest.fixture(scope="function")
def user_perms_app(custom_models: SimpleNamespace) -> Flask:
    """Create a Flask app for testing user permissions."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "User Permissions Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key-user-perms"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key-user-perms"

    init_fms(
        user=custom_models.CustomUserModel,
        role=custom_models.CustomUserRole,
        token=custom_models.CustomToken,
        domain=custom_models.CustomDomain,
        setting=custom_models.CustomUserSetting,
    )
    init_db(app)
    init_jwt(app)

    return app


@pytest.fixture(scope="function")
def db_session(user_perms_app: Flask) -> Iterator[scoped_session]:
    """Create a database session for tests."""
    with user_perms_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_users(
    custom_models: SimpleNamespace,
    user_perms_app: Flask,
    db_session: scoped_session,
) -> dict[str, uuid.UUID]:
    """Create test users with different roles and permissions."""
    CustomUserModel = custom_models.CustomUserModel
    CustomDomain = custom_models.CustomDomain
    CustomUserRole = custom_models.CustomUserRole

    # Create a domain
    domain = CustomDomain(name="test_domain", display_name="Test Domain")
    db_session.add(domain)
    db_session.commit()

    # Create users with different roles
    with CustomUserModel.bypass_perms():
        # Admin user (verified)
        admin_user = CustomUserModel(
            email="admin@example.com",
            password="admin_password",
            bio="Admin user bio",
            phone_number="111-111-1111",
            is_verified=True,
            roles=[CustomUserRole(role=BaseRoleEnum.ADMIN, domain_id=domain.id)],
        )
        db_session.add(admin_user)
        db_session.commit()

        # Regular verified user
        verified_user = CustomUserModel(
            email="verified@example.com",
            password="verified_password",
            bio="Verified user bio",
            phone_number="222-222-2222",
            is_verified=True,
            roles=[CustomUserRole(role=BaseRoleEnum.USER, domain_id=domain.id)],
        )
        db_session.add(verified_user)
        db_session.commit()

        # Regular unverified user
        unverified_user = CustomUserModel(
            email="unverified@example.com",
            password="unverified_password",
            bio="Unverified user bio",
            phone_number="333-333-3333",
            is_verified=False,
        )
        db_session.add(unverified_user)
        db_session.commit()

        # test adding role separately:
        unverified_role = CustomUserRole(user_id=unverified_user.id, role=BaseRoleEnum.USER, domain_id=domain.id)
        db_session.add(unverified_role)

        db_session.commit()

        # Return IDs instead of objects to avoid detached instance errors
        return {
            "admin_id": admin_user.id,
            "verified_id": verified_user.id,
            "unverified_id": unverified_user.id,
            "domain_id": domain.id,
        }


@pytest.fixture
def user_tokens(
    custom_models: SimpleNamespace,
    user_perms_app: Flask,
    db_session: scoped_session,
    test_users: dict[str, uuid.UUID],
) -> dict[str, str]:
    """JWT tokens for admin, verified, and unverified users."""
    CustomUserModel = custom_models.CustomUserModel

    with user_perms_app.app_context():
        admin_user = db_session.get(CustomUserModel, test_users["admin_id"])
        verified_user = db_session.get(CustomUserModel, test_users["verified_id"])
        unverified_user = db_session.get(CustomUserModel, test_users["unverified_id"])

    return {
        "admin": create_access_token(identity=admin_user.id),  # type: ignore[union-attr]
        "verified": create_access_token(identity=verified_user.id),  # type: ignore[union-attr]
        "unverified": create_access_token(identity=unverified_user.id),  # type: ignore[union-attr]
    }


class TestCustomUserModelExtension:
    """CustomUserModel class extension."""

    def test_custom_user_creation(
        self,
        custom_models: SimpleNamespace,
        db_session: scoped_session,
        test_users: dict[str, uuid.UUID],
    ) -> None:
        """Test that CustomUserModel can be created with custom fields."""
        CustomUserModel = custom_models.CustomUserModel
        user = db_session.get(CustomUserModel, test_users["verified_id"])
        assert user is not None
        assert user.email == "verified@example.com"
        assert user.bio == "Verified user bio"
        assert user.phone_number == "222-222-2222"
        assert user.is_verified is True

    def test_custom_user_inherits_user_methods(
        self,
        custom_models: SimpleNamespace,
        db_session: scoped_session,
        test_users: dict[str, uuid.UUID],
    ) -> None:
        """Test that CustomUserModel inherits User class methods."""
        CustomUserModel = custom_models.CustomUserModel
        user = db_session.get(CustomUserModel, test_users["verified_id"])
        assert user is not None
        # Test password methods
        assert user.is_password_correct("verified_password")
        assert not user.is_password_correct("wrong_password")

        # Test role methods
        assert user.has_role(BaseRoleEnum.USER)
        assert not user.has_role(BaseRoleEnum.ADMIN)

    def test_custom_user_custom_permissions(
        self,
        custom_models: SimpleNamespace,
        user_perms_app: Flask,
        db_session: scoped_session,
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """CustomUserModel' custom write permission requiring verification."""
        CustomUserModel = custom_models.CustomUserModel
        verified_user = db_session.get(CustomUserModel, test_users["verified_id"])
        unverified_user = db_session.get(CustomUserModel, test_users["unverified_id"])

        tokens = user_tokens
        verified_token = tokens["verified"]
        unverified_token = tokens["unverified"]
        admin_token = tokens["admin"]

        # Test verified user can write their own profile
        assert verified_user is not None
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {verified_token}"}):
            assert verified_user.can_write()
            verified_user.update(bio="Updated bio")  # Should not raise

        # Test unverified user cannot write (custom permission logic)
        assert unverified_user is not None
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {unverified_token}"}):
            assert not unverified_user.can_write()
            with pytest.raises(ForbiddenError):
                unverified_user.update(bio="Attempted update")  # Should raise

        # Test admin can write any profile
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {admin_token}"}):
            assert verified_user.can_write()
            verified_user.update(bio="Admin updated bio")  # Should not raise
            assert unverified_user.can_write()
            unverified_user.update(bio="Admin updated unverified bio")  # Should not raise
