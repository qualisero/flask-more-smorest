"""Maximal-use Flask app integration test.

This test demonstrates a complete Flask app configuration using all major features
of flask-more-smorest together, showing how streamlined and simple the setup can be.
"""

from typing import TYPE_CHECKING, Iterator
import pytest
import uuid

from flask import Flask
from flask_jwt_extended import create_access_token
from flask_more_smorest import CRUDBlueprint, BaseModel, db, Api, init_db, TimestampMixin, User

if TYPE_CHECKING:
    from flask.testing import FlaskClient


@pytest.fixture(scope="function")
def maximal_app() -> Flask:
    """Create a Flask app with maximal feature usage.

    This app demonstrates:
    - Database initialization with init_db
    - Custom models extending BaseModel with mixins
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

    # Initialize database
    init_db(app)
    from flask_jwt_extended import JWTManager

    jwt = JWTManager()
    jwt.init_app(app)
    jwt._set_error_handler_callbacks(app)

    return app


@pytest.fixture(scope="function")
def db_session(maximal_app: Flask):
    """Create a database session for tests."""
    with maximal_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def api(maximal_app: Flask, db_session) -> Api:
    """Create API instance."""
    return Api(maximal_app)


class Article(BaseModel, TimestampMixin):
    """Article model demonstrating multiple features."""

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=True)
    published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)

    # Relationship to User - no backref needed as we test in isolation
    author = db.relationship("User", foreign_keys=[author_id])

    def _can_read(self) -> bool:
        """Published articles can be read by anyone."""
        return self.published or self._can_write()

    def _can_write(self) -> bool:
        """Only the author can write."""
        from flask_more_smorest import get_current_user_id

        current_user_id = get_current_user_id()
        return current_user_id == self.author_id if current_user_id else True

    @classmethod
    def _can_create(cls) -> bool:
        """Anyone can create articles for this demo."""
        return True


class Comment(BaseModel, TimestampMixin):
    """Comment model for articles."""

    content = db.Column(db.Text, nullable=False)
    article_id = db.Column(db.UUID, db.ForeignKey(Article.id), nullable=False)
    author_id = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=True)

    # Relationships - no backref needed for testing
    article = db.relationship(Article, foreign_keys=[article_id])
    author = db.relationship("User", foreign_keys=[author_id])

    def _can_read(self) -> bool:
        """Comments are readable if article is readable."""
        return self.article._can_read() if self.article else True

    def _can_write(self) -> bool:
        """Only the comment author can edit."""
        from flask_more_smorest import get_current_user_id

        current_user_id = get_current_user_id()
        return current_user_id == self.author_id if current_user_id else True

    @classmethod
    def _can_create(cls) -> bool:
        """Anyone can create comments for this demo."""
        return True


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
    )

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


@pytest.fixture
def client(maximal_app: Flask, api: Api, blueprints: dict[str, CRUDBlueprint]) -> "FlaskClient":
    """Create test client with all blueprints registered."""
    api.register_blueprint(blueprints["articles"])
    api.register_blueprint(blueprints["comments"])
    return maximal_app.test_client()


@pytest.fixture(scope="function")
def test_user(db_session) -> Iterator[User]:
    """Create a test user."""

    u = User(email="test@test.com", password="password")
    db.session.add(u)
    db.session.commit()
    yield u
    db.session.delete(u)


@pytest.fixture(scope="function")
def auth_client(app: "Flask", client: "FlaskClient", test_user: "User") -> Iterator["FlaskClient"]:
    """Create an authenticated client for testing."""
    access_token = create_access_token(identity=test_user.id)
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
    yield client


class TestMaximalFeatureIntegration:
    """Integration tests demonstrating maximal feature usage."""

    def test_complete_article_lifecycle(self, auth_client: "FlaskClient", test_user: User) -> None:
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

        # Delete the article
        response = auth_client.delete(f"/api/articles/{article_id}")
        assert response.status_code in [200, 204]

    def test_filtering_articles(self, auth_client: "FlaskClient", maximal_app: Flask) -> None:
        """Test filtering functionality on articles."""
        # Create multiple articles
        articles_data = [
            {"title": "Published Article 1", "content": "Content 1", "published": True},
            {"title": "Published Article 2", "content": "Content 2", "published": True},
            {"title": "Draft Article", "content": "Content 3", "published": False},
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

    def test_related_models(self, db_session) -> None:
        """Test relationships between articles and comments."""

        # Create an article
        article = Article(
            title="Article with Comments",
            content="This article will have comments.",
            published=True,
        )
        db.session.add(article)
        db.session.commit()
        article_id = article.id

        # Create comments directly in database
        comment1 = Comment(content="Great article!", article_id=article_id)
        comment2 = Comment(content="Very informative.", article_id=article_id)
        db.session.add(comment1)
        db.session.add(comment2)
        db.session.commit()

        # Verify comments are associated
        comments: list = db.session.query(Comment).filter_by(article_id=article_id).all()
        assert len(comments) == 2
        assert comments[0].article_id == article_id
        assert comments[1].article_id == article_id

    def test_permissions_on_models(self, db_session) -> None:
        """Test permission system on models."""

        # Create a published article (readable by anyone)
        published_article = Article(title="Published", content="Public content", published=True)
        published_article.save()

        # Create a draft article (not published)
        draft_article = Article(title="Draft", content="Private content", published=False)
        draft_article.save()

        # Published article should be readable
        assert published_article.can_read() is True

        # Draft article readability depends on permission
        # In this case, since we're in bypass_perms, it should be readable
        assert draft_article.can_read() is True

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

    def test_timestamps_are_automatic(self, db_session) -> None:
        """Test that timestamps are automatically set and updated."""

        article = Article(title="Test", content="Test content", published=True)
        article.save()

        # Timestamps should be set
        assert article.created_at is not None
        assert article.updated_at is not None
        original_updated_at = article.updated_at

        # Update the article
        article.update(title="Updated Test")

        # updated_at should be newer
        assert article.updated_at >= original_updated_at

    def test_multiple_blueprints_coexist(self, auth_client, db_session) -> None:
        """Test that multiple CRUD blueprints work together."""

        # Both endpoints should be accessible
        response = auth_client.get("/api/articles/")
        assert response.status_code == 200

        response = auth_client.get("/api/comments/")
        assert response.status_code == 200

    def test_uuid_primary_keys(self, db_session) -> None:
        """Test that models use UUID primary keys."""

        article = Article(title="UUID Test", content="Testing UUID", published=True)
        article.save()

        # ID should be a UUID
        assert article.id is not None
        assert isinstance(article.id, uuid.UUID)

    def test_model_convenience_methods(self, db_session) -> None:
        """Test BaseModel convenience methods (get, get_or_404, etc.)."""

        article = Article(title="Test", content="Test", published=True)
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
