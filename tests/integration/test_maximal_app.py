"""Maximal-use Flask app integration test.

This test demonstrates a complete Flask app configuration using all major features
of flask-more-smorest together, showing how streamlined and simple the setup can be.
"""

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Callable, Iterator

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

from flask_more_smorest import (
    Api,
    BasePermsModel,
    CRUDBlueprint,
    CRUDMethod,
    DefaultUserRole,
    Domain,
    TimestampMixin,
    Token,
    User,
    UserCanReadWriteMixin,
    UserRole,
    UserSetting,
    db,
    init_db,
    init_jwt,
)
from flask_more_smorest.error import ForbiddenError, UnauthorizedError

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import scoped_session


@pytest.fixture(scope="function")
def maximal_app() -> Flask:
    """Create a Flask app with maximal feature usage.

    This app demonstrates:
    - Database initialization with init_db
    - Custom models extending BasePermsModel with mixins
    - CRUD blueprints with auto-generated endpoints
    - User management with roles
    - Permission-based access
    - Auto-generated schemas
    - Query filtering
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_TITLE"] = "Maximal Feature Demo API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.2"
    app.config["SECRET_KEY"] = "demo-secret-key"
    app.config["JWT_SECRET_KEY"] = "jwt-demo-secret-key"

    # Initialize database + JWT
    init_db(app)
    init_jwt(app)

    return app


@pytest.fixture(scope="function")
def db_session(maximal_app: Flask) -> Iterator["scoped_session"]:
    """Create a database session for tests."""
    with maximal_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def api(maximal_app: Flask, db_session: "scoped_session") -> Api:
    """Create API instance."""
    return Api(maximal_app)


class Article(UserCanReadWriteMixin, TimestampMixin, BasePermsModel):
    """Article model demonstrating multiple features."""

    __user_field_name__ = "author_id"
    __user_relationship_name__ = "author"

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)

    def _can_read(self) -> bool:
        """Published articles can be read by anyone."""
        return self.published or self.can_write()


class Comment(UserCanReadWriteMixin, TimestampMixin, BasePermsModel):
    """Comment model for articles."""

    __user_field_name__ = "author_id"
    __user_relationship_name__ = "author"

    content = db.Column(db.Text, nullable=False)
    article_id = db.Column(db.UUID, db.ForeignKey(Article.id), nullable=False)

    # Relationships - no backref needed for testing
    article = db.relationship(Article, foreign_keys=[article_id])

    def _can_read(self) -> bool:
        """Comments are readable if article is readable."""
        return self.article._can_read() if self.article else True


class Topic(TimestampMixin, BasePermsModel):
    """Topic model for articles.

    Only admins can create topics.
    """

    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationship to articles
    articles = db.relationship("Article", secondary="article_topics", backref="topics")

    def _can_create(self) -> bool:
        """Only admins can create topics."""
        return self.is_current_user_admin()


# Association table for Article-Topic many-to-many relationship
article_topics = db.Table(
    "article_topics",
    db.Column("article_id", db.UUID, db.ForeignKey("article.id"), primary_key=True),
    db.Column("topic_id", db.UUID, db.ForeignKey("topic.id"), primary_key=True),
)


@pytest.fixture(scope="function")
def blueprints() -> Iterator[dict[str, CRUDBlueprint]]:
    """Create CRUD blueprints for all models."""
    import sys
    import types

    # Create mock modules for blueprint imports
    articles_module = types.ModuleType("mock_articles")
    setattr(articles_module, "Article", Article)
    setattr(articles_module, "ArticleSchema", Article.Schema)
    sys.modules["mock_articles"] = articles_module

    comments_module = types.ModuleType("mock_comments")
    setattr(comments_module, "Comment", Comment)
    setattr(comments_module, "CommentSchema", Comment.Schema)
    sys.modules["mock_comments"] = comments_module

    # Create blueprints - use defaults where possible
    articles_bp = CRUDBlueprint(
        "articles",
        __name__,
        model="Article",
        model_import_name="mock_articles",
        schema_import_name="mock_articles",
        url_prefix="/api/articles/",
        methods={
            CRUDMethod.INDEX: True,
            CRUDMethod.GET: True,
            CRUDMethod.POST: True,
            CRUDMethod.PATCH: True,
            CRUDMethod.DELETE: {"admin_only": True},
        },
    )

    @articles_bp.public_endpoint
    @articles_bp.route("/health/")
    def articles_health() -> dict[str, str]:
        """Simple public endpoint for health checks."""
        return {"status": "ok"}

    comments_bp = CRUDBlueprint(
        "comments",
        __name__,
        model="Comment",
        model_import_name="mock_comments",
        schema_import_name="mock_comments",
        url_prefix="/api/comments/",
    )

    yield {"articles": articles_bp, "comments": comments_bp}

    # Cleanup
    if "mock_articles" in sys.modules:
        del sys.modules["mock_articles"]
    if "mock_comments" in sys.modules:
        del sys.modules["mock_comments"]


@pytest.fixture(scope="function")
def api_with_blueprints(api: Api, blueprints: dict[str, CRUDBlueprint]) -> Api:
    """Register all CRUD blueprints on the API."""
    api.register_blueprint(blueprints["articles"])
    api.register_blueprint(blueprints["comments"])
    return api


@pytest.fixture
def client(maximal_app: Flask, api_with_blueprints: Api, db_session: "scoped_session") -> "FlaskClient":
    """Create a base test client for unauthenticated requests."""
    _ = db_session
    return maximal_app.test_client()


@pytest.fixture(scope="function")
def token_factory(maximal_app: Flask) -> Callable[[uuid.UUID], str]:
    """Return a helper that issues JWTs for a given user ID."""

    def _issue(user_id: uuid.UUID) -> str:
        with maximal_app.app_context():
            return str(create_access_token(identity=user_id))

    return _issue


@pytest.fixture(scope="function")
def test_user(db_session: "scoped_session") -> Iterator[User]:
    """Create a test user."""

    u = User(email="test@test.com", password="password")
    db.session.add(u)
    db.session.commit()
    yield u
    # Clean up:
    u.delete()


@pytest.fixture(scope="function")
def test_other_user(db_session: "scoped_session") -> Iterator[User]:
    """Create another test user."""

    u = User(email="another@example.com", password="password2")
    db.session.add(u)
    db.session.commit()
    yield u
    # Clean up:
    u.delete()


@pytest.fixture(scope="function")
def admin_user(db_session: "scoped_session") -> Iterator[User]:
    """Create a user with admin privileges scoped to a domain."""

    domain = Domain(name="primary-domain", display_name="Primary Domain")
    admin = User(email="admin@test.com", password="password")
    db.session.add_all([domain, admin])
    db.session.commit()
    role = UserRole(user=admin, role=DefaultUserRole.ADMIN, domain=domain)
    db.session.add(role)
    db.session.commit()
    yield admin
    # Clean up:
    admin.delete()


@pytest.fixture(scope="function")
def auth_client(
    maximal_app: Flask,
    api_with_blueprints: Api,
    test_user: User,
    token_factory: Callable[[uuid.UUID], str],
) -> "FlaskClient":
    """Create an authenticated client for testing."""
    client = maximal_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token_factory(test_user.id)}"
    return client


@pytest.fixture(scope="function")
def other_auth_client(
    maximal_app: Flask,
    api_with_blueprints: Api,
    test_other_user: User,
    token_factory: Callable[[uuid.UUID], str],
) -> "FlaskClient":
    """Create an authenticated client for another test user."""
    client = maximal_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token_factory(test_other_user.id)}"
    return client


@pytest.fixture(scope="function")
def admin_client(
    maximal_app: Flask,
    api_with_blueprints: Api,
    admin_user: User,
    token_factory: Callable[[uuid.UUID], str],
) -> "FlaskClient":
    """Create an authenticated admin client for admin-only routes."""
    client = maximal_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token_factory(admin_user.id)}"
    return client


class TestMaximalFeatureIntegration:
    """Integration tests demonstrating maximal feature usage."""

    def test_pagination(self, auth_client: "FlaskClient", db_session: "scoped_session", test_user: User) -> None:
        """Test pagination functionality."""
        import json

        # Create 15 articles
        for i in range(15):
            article = Article(title=f"Page Article {i}", content="Content", published=True, author_id=test_user.id)
            db.session.add(article)
        db.session.commit()

        # Request page 1
        response = auth_client.get("/api/articles/", query_string={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 10

        # Verify pagination metadata in X-Pagination header
        assert "X-Pagination" in response.headers
        pagination_meta = json.loads(response.headers["X-Pagination"])
        assert pagination_meta["total"] == 15
        assert pagination_meta["total_pages"] == 2

        # Request page 2
        response = auth_client.get("/api/articles/", query_string={"page": 2, "page_size": 10})
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 5

        # Invalid page should return a validation error
        response = auth_client.get("/api/articles/", query_string={"page": 0, "page_size": 10})
        assert response.status_code == 422

        # Invalid page_size should return a validation error
        response = auth_client.get("/api/articles/", query_string={"page": 1, "page_size": 0})
        assert response.status_code == 422

    def test_complete_article_lifecycle(
        self,
        auth_client: "FlaskClient",
        admin_client: "FlaskClient",
        test_user: User,
    ) -> None:
        """Test complete CRUD lifecycle for articles."""

        # Create an article
        article_data = {
            "title": "Test Article",
            "content": "This is a comprehensive test article.",
            "published": True,
        }
        response = auth_client.post("/api/articles/", json=article_data)
        # CRUD blueprint returns 200 for POST
        assert response.status_code == 200, response.data
        article = response.get_json()
        article_id = article["id"]

        # # Read the article
        response = auth_client.get(f"/api/articles/{article_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Test Article"
        assert data["published"] is True
        assert "created_at" in data
        assert "updated_at" in data

        # # Update the article
        update_data = {"content": "Updated content"}
        response = auth_client.patch(f"/api/articles/{article_id}", json=update_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["content"] == "Updated content"
        assert data["title"] == "Test Article"  # Unchanged

        # List articles
        response = auth_client.get("/api/articles/")
        assert response.status_code == 200
        articles = response.get_json()
        assert len(articles) >= 1

        # Delete the article via admin-only endpoint
        response = admin_client.delete(f"/api/articles/{article_id}")
        assert response.status_code in [200, 204]

    def test_filtering_articles(self, auth_client: "FlaskClient", test_user: User) -> None:
        """Test filtering functionality on articles."""
        # Create multiple articles
        articles_data = [
            {"title": "Published Article 1", "content": "Content 1", "published": True, "author_id": test_user.id},
            {"title": "Published Article 2", "content": "Content 2", "published": True, "author_id": test_user.id},
            {"title": "Draft Article", "content": "Content 3", "published": False, "author_id": test_user.id},
        ]

        for data in articles_data:
            article = Article(**data)
            db.session.add(article)
        db.session.commit()

        # Filter for published articles
        response = auth_client.get("/api/articles/", query_string={"published": "true"})
        assert response.status_code == 200
        articles = response.get_json()
        assert len(articles) == 2
        assert all(a["published"] is True for a in articles)

    def test_related_models(self, db_session: "scoped_session", test_user: User) -> None:
        """Test relationships between articles and comments."""

        # Create an article
        article = Article(
            title="Article with Comments",
            content="This article will have comments.",
            published=True,
            author_id=test_user.id,
        )
        db.session.add(article)
        db.session.commit()
        article_id = article.id

        # Create comments directly in database
        comment1 = Comment(content="Great article!", article_id=article_id, author_id=test_user.id)
        comment2 = Comment(content="Very informative.", article_id=article_id, author_id=test_user.id)
        db.session.add(comment1)
        db.session.add(comment2)
        db.session.commit()

        # Verify comments are associated
        comments: list = db.session.query(Comment).filter_by(article_id=article_id).all()
        assert len(comments) == 2
        assert comments[0].article_id == article_id
        assert comments[1].article_id == article_id

    def test_permissions_on_models(
        self,
        db_session: "scoped_session",
        auth_client: "FlaskClient",
        other_auth_client: "FlaskClient",
        admin_client: "FlaskClient",
        test_user: User,
    ) -> None:
        """Test permission system on models."""

        # Create a published article (readable by anyone)
        published_article = Article(title="Published", content="Public content", published=True, author_id=test_user.id)
        published_article.save()

        # Create a draft article (not published)
        draft_article = Article(title="Draft", content="Private content", published=False, author_id=test_user.id)
        draft_article.save()

        # Published article should be readable by anyone
        assert published_article.can_read() is True
        res = auth_client.get(f"/api/articles/{published_article.id}")
        assert res.status_code == 200
        res = other_auth_client.get(f"/api/articles/{published_article.id}")
        assert res.status_code == 200
        res = admin_client.get(f"/api/articles/{published_article.id}")
        assert res.status_code == 200

        # Draft article readability depends on permission
        assert draft_article.can_read() is True
        res = auth_client.get(f"/api/articles/{draft_article.id}")
        assert res.status_code == 200

        with pytest.raises(ForbiddenError):
            other_auth_client.get(f"/api/articles/{draft_article.id}")

        res = admin_client.get(f"/api/articles/{draft_article.id}")
        assert res.status_code == 200

    def test_auto_generated_schema_fields(self) -> None:
        """Test that auto-generated schemas include all expected fields."""

        schema = Article.Schema()

        # BaseModel fields
        assert "id" in schema.fields
        assert "created_at" in schema.fields
        assert "updated_at" in schema.fields
        assert "is_writable" in schema.fields

        # Article-specific fields
        assert "title" in schema.fields
        assert "content" in schema.fields
        assert "published" in schema.fields
        assert "view_count" in schema.fields

    def test_timestamps_are_automatic(self, db_session: "scoped_session", test_user: User) -> None:
        """Test that timestamps are automatically set and updated."""

        article = Article(title="Test", content="Test content", published=True, author_id=test_user.id)
        article.save()

        # Timestamps should be set
        assert article.created_at is not None
        assert article.updated_at is not None
        original_updated_at = article.updated_at

        # Update the article
        article.update(title="Updated Test")

        # updated_at should be newer
        assert article.updated_at >= original_updated_at

    def test_multiple_blueprints_coexist(self, auth_client: "FlaskClient", db_session: "scoped_session") -> None:
        """Test that multiple CRUD blueprints work together."""

        # Both endpoints should be accessible
        response = auth_client.get("/api/articles/")
        assert response.status_code == 200

        response = auth_client.get("/api/comments/")
        assert response.status_code == 200

    def test_uuid_primary_keys(self, db_session: "scoped_session", test_user: User) -> None:
        """Test that models use UUID primary keys."""

        article = Article(title="UUID Test", content="Testing UUID", published=True, author_id=test_user.id)
        article.save()

        # ID should be a UUID
        assert article.id is not None
        assert isinstance(article.id, uuid.UUID)

    def test_model_convenience_methods(self, db_session: "scoped_session", test_user: User) -> None:
        """Test BaseModel convenience methods (get, get_or_404, etc.)."""

        article = Article(title="Test", content="Test", published=True, author_id=test_user.id)
        article.save()
        article_id = article.id

        # Test get method
        retrieved = Article.get(article_id)
        assert retrieved is not None
        assert retrieved.id == article_id

        # Test get_or_404
        retrieved = Article.get_or_404(article_id)
        assert retrieved.id == article_id

        with pytest.raises(Exception):
            assert Article.get_or_404(uuid.uuid4())

        # Test get_by
        retrieved = Article.get_by(title="Test")
        assert retrieved is not None
        assert retrieved.title == "Test"

        # Test get_by_or_404
        retrieved = Article.get_by_or_404(title="Test")
        assert retrieved.title == "Test"

        with pytest.raises(Exception):
            Article.get_by_or_404(title="Nonexistent")

    def test_auth_required_for_private_routes(self, client: "FlaskClient") -> None:
        """Private endpoints should reject unauthenticated requests."""

        with pytest.raises(UnauthorizedError):
            client.get("/api/articles/")

    def test_public_health_endpoint_is_public(self, client: "FlaskClient") -> None:
        """Public endpoints can be called without authentication."""

        response = client.get("/api/articles/health/")
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}

    def test_admin_only_delete_requires_role(
        self,
        auth_client: "FlaskClient",
        admin_client: "FlaskClient",
    ) -> None:
        """Ensure admin-only CRUD routes enforce role checks."""

        article_data = {
            "title": "Needs Admin",
            "content": "Only admins can delete this.",
            "published": True,
        }
        create_resp = auth_client.post("/api/articles/", json=article_data)
        assert create_resp.status_code == 200
        article_id = create_resp.get_json()["id"]

        with pytest.raises(ForbiddenError):
            auth_client.delete(f"/api/articles/{article_id}")

        admin_resp = admin_client.delete(f"/api/articles/{article_id}")
        assert admin_resp.status_code in {200, 204}

    def test_operation_ids_generated(self, api_with_blueprints: Api) -> None:
        """The Api should expose camelCase operationIds for CRUD routes."""

        assert api_with_blueprints.spec is not None
        spec = api_with_blueprints.spec.to_dict()
        assert spec["paths"]["/api/articles/"]["get"]["operationId"] == "listArticle"
        assert spec["paths"]["/api/articles/{articles_id}"]["delete"]["operationId"] == "deleteArticle"

    def test_advanced_filter_range_queries(
        self, auth_client: "FlaskClient", db_session: "scoped_session", test_user: User
    ) -> None:
        """Query parameters with __min/__from suffixes should filter results."""

        base_time = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        for idx in range(3):
            article = Article(
                title=f"Range Article {idx}",
                content="Range content",
                published=True,
                view_count=idx * 10,
                author_id=test_user.id,
            )
            article.save()
            article.created_at = base_time + dt.timedelta(days=idx)
        db.session.commit()

        query = {
            "view_count__min": 10,
            "created_at__from": (base_time + dt.timedelta(days=1, seconds=-1)).isoformat(),
            "created_at__to": (base_time + dt.timedelta(days=1, seconds=1)).isoformat(),
        }
        response = auth_client.get("/api/articles/", query_string=query)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Range Article 1"

    def test_user_domain_role_and_token_models(self, db_session: "scoped_session") -> None:
        """Domain, UserRole, Token, and UserSetting models integrate end-to-end."""

        domain = Domain(name="tenant-a", display_name="Tenant A")
        user = User(email="role@test.com", password="password")
        db.session.add_all([domain, user])
        db.session.commit()

        role = UserRole(user=user, role=DefaultUserRole.ADMIN, domain=domain)
        setting = UserSetting(user=user, key="theme", value="dark")
        token = Token(user=user, token="secret-token")
        db.session.add_all([role, setting, token])
        db.session.commit()

        assert user.has_role(DefaultUserRole.ADMIN)
        assert user.has_domain_access(domain.id)
        assert user.num_tokens == 1
        assert user.settings[0].value == "dark"

        with UserRole.bypass_perms():
            role.delete()
        db.session.expire(user, ["roles"])
        assert user.roles == []

    def test_get_clone_creates_distinct_record(self, db_session: "scoped_session", test_user: User) -> None:
        """BaseModel.get_clone should produce a detached copy with new UUID."""

        article = Article(title="Original", content="Original content", published=True, author_id=test_user.id)
        article.save()
        original_id = article.id

        clone = article.get_clone()
        clone.title = "Original (Clone)"
        clone.save()

        assert Article.get_or_404(original_id).title == "Original"
        assert Article.get_by(title="Original (Clone)") is not None
        assert db.session.query(Article).count() == 2
        assert clone.id != original_id

    def test_update_permission_enforcement(
        self,
        auth_client: "FlaskClient",
        other_auth_client: "FlaskClient",
        test_user: User,
    ) -> None:
        """User cannot update an article they don't own."""

        # User A creates article
        article = Article(title="My Article", content="Content", published=True, author_id=test_user.id)
        article.save()

        # User B tries to update via API (PATCH)
        update_data = {"content": "Hacked content"}

        with pytest.raises(ForbiddenError):
            other_auth_client.patch(f"/api/articles/{article.id}", json=update_data)

    def test_delete_permission_enforcement(
        self,
        auth_client: "FlaskClient",
        other_auth_client: "FlaskClient",
        test_user: User,
    ) -> None:
        """User cannot delete an article they don't own."""

        article = Article(title="My Article", content="Content", published=True, author_id=test_user.id)
        article.save()

        # User B tries to delete via API
        # Note: DELETE endpoint is admin-only in blueprint config, so it returns 403 anyway,
        # but this confirms that permission checks are enforced.
        with pytest.raises(ForbiddenError):
            other_auth_client.delete(f"/api/articles/{article.id}")

    def test_admin_override_permissions(
        self,
        admin_client: "FlaskClient",
        test_user: User,
    ) -> None:
        """Admin can update/delete articles owned by others."""

        article = Article(title="User Article", content="Content", published=True, author_id=test_user.id)
        article.save()

        # Admin updates
        response = admin_client.patch(f"/api/articles/{article.id}", json={"content": "Admin Edit"})
        assert response.status_code == 200

        # Verify update
        assert Article.get_or_404(article.id).content == "Admin Edit"

        # Admin deletes
        response = admin_client.delete(f"/api/articles/{article.id}")
        assert response.status_code in (200, 204)

        assert Article.get(article.id) is None

    def test_bypass_perms_context_manager(self, test_user: User) -> None:
        """Context manager should bypass permission checks."""

        article = Article(title="Test", content="Content", published=True, author_id=test_user.id)
        article.save()

        # We can force perms_disabled = True explicitly.
        with Article.bypass_perms():
            assert Article.perms_disabled is True
            article.delete()

        assert Article.get(article.id) is None

    def test_unauthorized_direct_access_fails(self, client: "FlaskClient", test_user: User) -> None:
        """Direct model access without auth should fail if request context exists."""

        # Create a draft article (private)
        article = Article(title="Test", content="Content", published=False, author_id=test_user.id)
        article.save()

        # client context has request context but no user
        with client.application.test_request_context("/"):
            # Request context active, but no JWT.
            # can_read should return False (access denied for anonymous).
            assert article.can_read() is False

    def test_create_permission_restriction(
        self, auth_client: "FlaskClient", admin_client: "FlaskClient", test_user: User
    ) -> None:
        """Only admins can create Topics."""

        # Normal user tries to create Topic
        topic = Topic(name="Restricted")

        # Use auth_client context to simulate normal user
        token = auth_client.environ_base["HTTP_AUTHORIZATION"]

        with auth_client.application.test_request_context("/", headers={"Authorization": token}):
            # Now we are "logged in" as test_user
            assert topic.is_current_user_admin() is False

            with pytest.raises(ForbiddenError):
                topic.save()
