"""Integration tests for User model extension with permissions checking.

This test demonstrates:
- Creating a CustomUser class that extends the package's User class
- Testing user-related default tables (settings, tokens, roles)
- Testing a model with UserCanReadWriteMixin for permission access
- Testing a model with custom permission rules
"""

import uuid
from typing import TYPE_CHECKING, Iterator

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flask_more_smorest import (
    DefaultUserRole,
    Domain,
    Token,
    User,
    UserRole,
    UserSetting,
    db,
    get_current_user_id,
    init_db,
    init_jwt,
)
from flask_more_smorest.error.exceptions import ForbiddenError
from flask_more_smorest.perms.base_perms_model import BasePermsModel
from flask_more_smorest.perms.model_mixins import UserCanReadWriteMixin

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import scoped_session


@pytest.fixture(scope="function")
def user_perms_app() -> Flask:
    """Create a Flask app for testing user permissions.

    This app demonstrates:
    - Custom User model extending the base User class
    - User-related tables (settings, tokens, roles)
    - Models with various permission rules
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "User Permissions Test API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "test-secret-key-user-perms"
    app.config["JWT_SECRET_KEY"] = "jwt-test-secret-key-user-perms"

    init_db(app)
    init_jwt(app)

    return app


@pytest.fixture(scope="function")
def db_session(user_perms_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with user_perms_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


class CustomUser(User):
    """Custom User class that extends the base User class.

    Adds additional fields specific to this application:
    - bio: User biography
    - phone_number: Contact phone number
    - is_verified: Whether the user has been verified
    """

    __tablename__ = "custom_users"

    bio: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    is_verified: Mapped[bool] = mapped_column(sa.Boolean(), default=False)

    def _can_write(self) -> bool:
        """Override write permission to require verification.

        Only verified users can edit their own profiles.
        Admins can edit any profile regardless of verification.
        """
        # Allow admins to write
        if self.is_current_user_admin():
            return True

        # Check if user is editing their own profile
        current_user_id = get_current_user_id()
        if current_user_id != self.id:
            return False

        # Require verification for self-edit
        return self.is_verified


class Note(UserCanReadWriteMixin, BasePermsModel):
    """Note model with UserCanReadWriteMixin.

    This model demonstrates user-owned resources where:
    - Users can only read their own notes
    - Users can only write their own notes
    """

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

    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(sa.Boolean(), default=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey(CustomUser.id),
        nullable=False,
    )

    owner: Mapped["CustomUser"] = relationship(CustomUser)

    def _can_read(self) -> bool:
        """Custom read permission: public docs readable by all, private only by owner."""
        if self.is_public:
            return True

        current_user_id = get_current_user_id()
        return current_user_id == self.owner_id if current_user_id else False

    def _can_write(self) -> bool:
        """Custom write permission: only owner can write."""
        current_user_id = get_current_user_id()
        return current_user_id == self.owner_id if current_user_id else False

    def _can_create(self) -> bool:
        """Custom create permission: only verified users can create documents."""
        current_user_id = get_current_user_id()
        if not current_user_id:
            return False

        owner = db.session.get(CustomUser, current_user_id)
        return owner.is_verified if owner else False


@pytest.fixture
def client(user_perms_app: Flask) -> "FlaskClient":
    """Create test client."""
    return user_perms_app.test_client()


@pytest.fixture
def test_users(user_perms_app: Flask, db_session: "scoped_session") -> dict[str, uuid.UUID]:
    """Create test users with different roles and permissions.

    Returns user IDs instead of user objects to avoid detached instance issues.
    """
    # Create a domain
    domain = Domain(name="test_domain", display_name="Test Domain")
    db_session.add(domain)
    db_session.commit()

    # Create users with different roles
    with CustomUser.bypass_perms():
        # Admin user (verified)
        admin_user = CustomUser(
            email="admin@example.com",
            password="admin_password",
            bio="Admin user bio",
            phone_number="111-111-1111",
            is_verified=True,
            roles=[UserRole(role=DefaultUserRole.ADMIN, domain_id=domain.id)],
        )
        db_session.add(admin_user)
        db_session.commit()

        # Regular verified user
        verified_user = CustomUser(
            email="verified@example.com",
            password="verified_password",
            bio="Verified user bio",
            phone_number="222-222-2222",
            is_verified=True,
            roles=[UserRole(role=DefaultUserRole.USER, domain_id=domain.id)],
        )
        db_session.add(verified_user)
        db_session.commit()

        # Regular unverified user
        unverified_user = CustomUser(
            email="unverified@example.com",
            password="unverified_password",
            bio="Unverified user bio",
            phone_number="333-333-3333",
            is_verified=False,
        )
        db_session.add(unverified_user)
        db_session.commit()

        # test adding role separately:
        unverified_role = UserRole(user_id=unverified_user.id, role=DefaultUserRole.USER, domain_id=domain.id)
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
    user_perms_app: Flask,
    db_session: "scoped_session",
    test_users: dict[str, uuid.UUID],
) -> dict[str, str]:
    """JWT tokens for admin, verified, and unverified users."""

    with user_perms_app.app_context():
        admin_user = db_session.get(CustomUser, test_users["admin_id"])
        verified_user = db_session.get(CustomUser, test_users["verified_id"])
        unverified_user = db_session.get(CustomUser, test_users["unverified_id"])

    return {
        "admin": create_access_token(identity=admin_user),
        "verified": create_access_token(identity=verified_user),
        "unverified": create_access_token(identity=unverified_user),
    }


class TestCustomUserExtension:
    """Test CustomUser class extension."""

    def test_custom_user_creation(self, db_session: "scoped_session", test_users: dict[str, uuid.UUID]) -> None:
        """Test that CustomUser can be created with custom fields."""
        user = db_session.get(CustomUser, test_users["verified_id"])
        assert user is not None
        assert user.email == "verified@example.com"
        assert user.bio == "Verified user bio"
        assert user.phone_number == "222-222-2222"
        assert user.is_verified is True

    def test_custom_user_inherits_user_methods(
        self, db_session: "scoped_session", test_users: dict[str, uuid.UUID]
    ) -> None:
        """Test that CustomUser inherits User class methods."""
        user = db_session.get(CustomUser, test_users["verified_id"])
        assert user is not None
        # Test password methods
        assert user.is_password_correct("verified_password")
        assert not user.is_password_correct("wrong_password")

        # Test role methods
        assert user.has_role(DefaultUserRole.USER)
        assert not user.has_role(DefaultUserRole.ADMIN)

    def test_custom_user_custom_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test CustomUser's custom write permission requiring verification."""
        verified_user = db_session.get(CustomUser, test_users["verified_id"])
        unverified_user = db_session.get(CustomUser, test_users["unverified_id"])

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


class TestUserRelatedTables:
    """Test user-related default tables (settings, tokens, roles)."""

    def test_user_settings(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test UserSetting creation and retrieval."""
        user = db_session.get(CustomUser, test_users["verified_id"])
        assert user is not None

        tokens = user_tokens

        # Create user settings
        setting1 = UserSetting(user_id=user.id, key="theme", value="dark")
        db_session.add(setting1)
        db_session.commit()

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['verified']}"}):
            setting2 = UserSetting(user_id=user.id, key="language", value="en")
            setting2.save()  # Using save() method

        other_token = tokens["unverified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {other_token}"}):
            # Attempt to create setting for another user should fail
            setting3 = UserSetting(user_id=user.id, key="timezone", value="UTC")
            with pytest.raises(ForbiddenError):
                setting3.save()  # Should raise

            # Attempt to read another user's settings should fail
            assert not setting1.can_read()
            with pytest.raises(ForbiddenError):
                UserSetting.get(setting1.id)  # Should raise

            # Attempt to modify another user's setting should fail
            assert not setting1.can_write()
            with pytest.raises(ForbiddenError):
                setting1.update(value="light")  # Should raise

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['verified']}"}):
            assert setting1.can_read()
            assert setting2.can_read()
            setting2.update(value="fr")  # Should not raise

            user_settings = UserSetting.query.filter_by(user_id=user.id).all()

        # Verify settings are associated with user
        assert len(user_settings) == 2
        setting_keys = {s.key for s in user_settings}
        assert "theme" in setting_keys
        assert "language" in setting_keys

        # Verify setting values
        theme_setting = next(s for s in user_settings if s.key == "theme")
        assert theme_setting.value == "dark"

        language_setting = next(s for s in user_settings if s.key == "language")
        assert language_setting.value == "fr"

    def test_user_tokens(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test Token creation and retrieval."""
        user = db_session.get(CustomUser, test_users["verified_id"])
        assert user is not None

        # Create tokens
        token1 = Token(user_id=user.id, token="test_token_1", description="API Token 1")
        db_session.add(token1)
        db_session.commit()

        tokens = user_tokens
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['verified']}"}):
            token2 = Token(user_id=user.id, token="test_token_2", description="API Token 2")
            token2.save()  # Using save() method

        # Verify tokens are associated with user
        assert user.num_tokens == 2
        assert len(user.tokens) == 2

        # Verify token values
        token_descriptions = {t.description for t in user.tokens}
        assert "API Token 1" in token_descriptions
        assert "API Token 2" in token_descriptions

    def test_user_roles(self, db_session: "scoped_session", test_users: dict[str, uuid.UUID]) -> None:
        """Test UserRole creation and retrieval."""
        admin_user = db_session.get(CustomUser, test_users["admin_id"])
        regular_user = db_session.get(CustomUser, test_users["verified_id"])

        # Verify admin user has admin role
        assert admin_user is not None
        assert admin_user.is_admin
        assert admin_user.has_role(DefaultUserRole.ADMIN)
        assert len(admin_user.roles) == 1

        # Verify regular user has user role
        assert regular_user is not None
        assert not regular_user.is_admin
        assert regular_user.has_role(DefaultUserRole.USER)
        assert not regular_user.has_role(DefaultUserRole.ADMIN)


class TestUserCanReadWriteMixin:
    """Test Note model with UserCanReadWriteMixin."""

    def test_note_creation_and_ownership(self, db_session: "scoped_session", test_users: dict[str, uuid.UUID]) -> None:
        """Test that notes are created with proper ownership."""
        user = db_session.get(CustomUser, test_users["verified_id"])
        assert user is not None

        note = Note(user_id=user.id, title="My Note", content="Note content")
        db_session.add(note)
        db_session.commit()

        # Verify note ownership
        assert note.user_id == user.id
        assert note.user.email == user.email

    def test_note_read_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that users can only read their own notes."""
        user1 = db_session.get(CustomUser, test_users["verified_id"])
        user2 = db_session.get(CustomUser, test_users["unverified_id"])
        assert user1 is not None
        assert user2 is not None

        note = Note(user_id=user1.id, title="User1's Note", content="Private content")
        db_session.add(note)
        db_session.commit()

        tokens = user_tokens
        user1_token = tokens["verified"]
        user2_token = tokens["unverified"]

        # Test user1 can read their own note
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {user1_token}"}):
            assert note.can_read()

        # Test user2 cannot read user1's note
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {user2_token}"}):
            assert not note.can_read()

    def test_note_write_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that users can only write their own notes."""
        user1 = db_session.get(CustomUser, test_users["verified_id"])
        user2 = db_session.get(CustomUser, test_users["unverified_id"])
        assert user1 is not None
        assert user2 is not None

        note = Note(user_id=user1.id, title="User1's Note", content="Private content")
        db_session.add(note)
        db_session.commit()

        tokens = user_tokens
        user1_token = tokens["verified"]
        user2_token = tokens["unverified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {user1_token}"}):
            assert note.can_write()
            note.update(content="Updated content")

        # Test user2 cannot write user1's note
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {user2_token}"}):
            assert not note.can_write()
            with pytest.raises(ForbiddenError):
                note.update(content="Malicious update")


class TestCustomPermissionRules:
    """Test Document model with custom permission rules."""

    def test_public_document_read_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that public documents can be read by anyone."""
        owner = db_session.get(CustomUser, test_users["verified_id"])
        other_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert owner is not None
        assert other_user is not None

        public_doc = Document(
            owner_id=owner.id,
            title="Public Document",
            content="Public content",
            is_public=True,
        )
        db_session.add(public_doc)
        db_session.commit()

        # Test owner can read
        tokens = user_tokens
        owner_token = tokens["verified"]
        other_token = tokens["unverified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {owner_token}"}):
            assert public_doc.can_read()

        # Test other user can read public document
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {other_token}"}):
            assert public_doc.can_read()

    def test_private_document_read_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that private documents can only be read by owner."""
        owner = db_session.get(CustomUser, test_users["verified_id"])
        other_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert owner is not None
        assert other_user is not None

        private_doc = Document(
            owner_id=owner.id,
            title="Private Document",
            content="Private content",
            is_public=False,
        )
        db_session.add(private_doc)
        db_session.commit()

        # Test owner can read
        tokens = user_tokens
        owner_token = tokens["verified"]
        other_token = tokens["unverified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {owner_token}"}):
            assert private_doc.can_read()

        # Test other user cannot read private document
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {other_token}"}):
            assert not private_doc.can_read()

    def test_document_write_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that only owner can write documents."""
        owner = db_session.get(CustomUser, test_users["verified_id"])
        other_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert owner is not None
        assert other_user is not None

        doc = Document(
            owner_id=owner.id,
            title="Document",
            content="Content",
            is_public=True,
        )
        db_session.add(doc)
        db_session.commit()

        # Test owner can write
        tokens = user_tokens
        owner_token = tokens["verified"]
        other_token = tokens["unverified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {owner_token}"}):
            assert doc.can_write()
            doc.update(content="Owner updated content")

        # Test other user cannot write even if document is public
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {other_token}"}):
            assert not doc.can_write()
            with pytest.raises(ForbiddenError):
                doc.update(content="Malicious update")

    def test_document_create_permissions(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Test that only verified users can create documents."""
        verified_user = db_session.get(CustomUser, test_users["verified_id"])
        unverified_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert verified_user is not None
        assert unverified_user is not None

        # Test verified user can create
        tokens = user_tokens
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['verified']}"}):
            doc1 = Document(
                owner_id=verified_user.id,
                title="New Document",
                content="Content",
                is_public=False,
            )
            assert doc1.can_create()
            doc1.save()  # Should not raise

        # Test unverified user cannot create
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['unverified']}"}):
            doc2 = Document(
                owner_id=unverified_user.id,
                title="New Document",
                content="Content",
                is_public=False,
            )
            assert not doc2.can_create()
            with pytest.raises(ForbiddenError):
                doc2.save()

    def test_private_document_requires_authentication_for_read_write(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Ensure private documents require authentication even for reads/writes."""
        owner = db_session.get(CustomUser, test_users["verified_id"])
        other_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert owner is not None
        assert other_user is not None

        private_doc = Document(
            owner_id=owner.id,
            title="Blocked",
            content="Secret",
            is_public=False,
        )
        db_session.add(private_doc)
        db_session.commit()

        tokens = user_tokens
        owner_token = tokens["verified"]

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {owner_token}"}):
            assert private_doc.can_read()
            assert private_doc.can_write()

        # Without authentication, permission checks should deny access
        with user_perms_app.test_request_context():
            assert not private_doc.can_read()
            assert not private_doc.can_write()

        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['unverified']}"}):
            assert not private_doc.can_read()
            assert not private_doc.can_write()

    def test_bypass_perms_allows_forced_creation_for_blocked_user(
        self,
        user_perms_app: Flask,
        db_session: "scoped_session",
        test_users: dict[str, uuid.UUID],
        user_tokens: dict[str, str],
    ) -> None:
        """Bypass permissions to create a document even when user lacks rights."""
        unverified_user = db_session.get(CustomUser, test_users["unverified_id"])
        assert unverified_user is not None

        tokens = user_tokens
        with user_perms_app.test_request_context(headers={"Authorization": f"Bearer {tokens['unverified']}"}):
            doc = Document(
                owner_id=unverified_user.id,
                title="Denied",
                content="No rights",
                is_public=False,
            )
            assert not doc.can_create()
            with pytest.raises(ForbiddenError):
                doc.save()

        with Document.bypass_perms():
            forced_doc = Document(
                owner_id=unverified_user.id,
                title="Forced",
                content="Allowed",
                is_public=False,
            )
            forced_doc.save()

        assert db_session.get(Document, forced_doc.id) is not None
