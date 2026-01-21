"""Tests for ApiException responses and RFC 7807 compliance."""

from __future__ import annotations

from http import HTTPStatus

from flask import Flask

from flask_more_smorest.error.exceptions import (
    ApiException,
    ForbiddenError,
    UnauthorizedError,
    _is_debug_mode,
)


class DummyException(ApiException):
    TITLE = "Dummy Error"
    HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST


class NoTracebackException(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    INCLUDE_TRACEBACK = False


class ExplicitTracebackException(ApiException):
    TITLE = "Explicit Traceback Error"
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    INCLUDE_TRACEBACK = True


def test_is_debug_mode_outside_app_context() -> None:
    """Test that _is_debug_mode returns False without app context."""
    assert _is_debug_mode() is False


def test_is_debug_mode_in_debug_app() -> None:
    """Test that _is_debug_mode returns True in debug mode."""
    app = Flask(__name__)
    app.config["DEBUG"] = True
    with app.app_context():
        assert _is_debug_mode() is True


def test_is_debug_mode_in_testing_app() -> None:
    """Test that _is_debug_mode returns True in testing mode."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    with app.app_context():
        assert _is_debug_mode() is True


def test_is_debug_mode_in_production() -> None:
    """Test that _is_debug_mode returns False in production."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    with app.app_context():
        assert _is_debug_mode() is False


def test_api_exception_includes_debug_context_in_debug_mode() -> None:
    """Test that debug context is included when DEBUG=True."""
    app = Flask(__name__)
    app.config["DEBUG"] = True

    with app.app_context():
        try:
            raise DummyException("problem", extra="info")
        except DummyException as exc:
            response = exc.make_error_response()

    payload = response.get_json()

    # RFC 7807 format
    assert payload["status"] == HTTPStatus.BAD_REQUEST
    assert payload["title"] == "Dummy Error"
    assert payload["detail"] == "problem"
    assert "fields" in payload
    assert payload["fields"]["extra"] == "info"

    # Debug info present in debug mode
    assert "debug" in payload
    assert payload["debug"]["context"]["extra"] == "info"
    assert "traceback" in payload["debug"]


def test_api_exception_excludes_debug_in_production() -> None:
    """Test that debug context is NOT included in production mode."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    with app.app_context():
        try:
            raise DummyException("problem", extra="info")
        except DummyException as exc:
            response = exc.make_error_response()

    payload = response.get_json()
    assert payload["status"] == HTTPStatus.BAD_REQUEST
    assert payload["fields"]["extra"] == "info"
    # Debug should NOT be included in production
    assert "debug" not in payload


def test_api_exception_trims_traceback_when_disabled() -> None:
    """Test that traceback is excluded when INCLUDE_TRACEBACK=False."""
    app = Flask(__name__)
    app.config["DEBUG"] = True  # Even with debug on

    with app.app_context():
        try:
            raise NoTracebackException("fail")
        except NoTracebackException as exc:
            response = exc.make_error_response()

    payload = response.get_json()
    # Debug is included because we're in debug mode
    assert "debug" in payload
    # But traceback is explicitly disabled
    assert "traceback" not in payload["debug"]


def test_api_exception_explicit_traceback_in_production() -> None:
    """Test that explicit INCLUDE_TRACEBACK=True still excludes debug in production."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    with app.app_context():
        try:
            raise ExplicitTracebackException("fail")
        except ExplicitTracebackException as exc:
            response = exc.make_error_response()

    payload = response.get_json()
    # Even with explicit traceback, debug block is not included in production
    assert "debug" not in payload


def test_subclass_without_extra_kwargs() -> None:
    """Test UnauthorizedError message handling."""
    app = Flask(__name__)
    app.config["DEBUG"] = True

    with app.app_context():
        response = UnauthorizedError("no token").make_error_response()

    payload = response.get_json()
    assert payload["detail"] == "no token"
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    # UnauthorizedError has INCLUDE_TRACEBACK=False explicitly
    if "debug" in payload:
        assert "traceback" not in payload["debug"]


def test_unauthorized_error_never_includes_traceback() -> None:
    """Test that UnauthorizedError never includes traceback for security."""
    app = Flask(__name__)
    app.config["DEBUG"] = True

    with app.app_context():
        try:
            raise UnauthorizedError("forbidden")
        except UnauthorizedError as exc:
            response = exc.make_error_response()

    payload = response.get_json()
    # UnauthorizedError explicitly sets INCLUDE_TRACEBACK=False
    # so even in debug mode, no traceback
    if "debug" in payload:
        assert "traceback" not in payload["debug"]


def test_forbidden_error_uses_environment_detection() -> None:
    """Test that ForbiddenError uses environment-aware traceback."""
    app = Flask(__name__)
    app.config["DEBUG"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    # ForbiddenError has INCLUDE_TRACEBACK=None (uses environment detection)
    assert ForbiddenError.INCLUDE_TRACEBACK is None


def test_content_type_is_problem_json() -> None:
    """Test that response has RFC 7807 content type."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.app_context():
        response = DummyException("test").make_error_response()

    assert response.content_type == "application/problem+json"


def test_user_context_included_in_debug_mode() -> None:
    """Test that user context is included in debug mode using configurable user context."""
    import uuid

    from flask_more_smorest import init_jwt
    from flask_more_smorest.perms.user_context import (
        clear_registration,
        register_user_class,
    )

    app = Flask(__name__)
    app.config["DEBUG"] = True
    app.config["JWT_SECRET_KEY"] = "test-secret-key"
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    init_jwt(app)

    # Set up mock user context
    test_user_id = uuid.uuid4()

    class MockUser:
        def __init__(self):
            self.id = test_user_id
            self.roles = [type("Role", (), {"role": "admin"})]

        def has_role(self, role: str) -> bool:
            return role == "admin"

        def list_roles(self) -> list[str]:
            return ["admin"]

    def get_mock_user():
        return MockUser()

    try:
        with app.app_context():
            register_user_class(MockUser, get_current_user=get_mock_user)
            with app.test_request_context():
                try:
                    raise DummyException("test error")
                except DummyException as exc:
                    response = exc.make_error_response()

        payload = response.get_json()

        # Should have debug context in debug mode
        assert "debug" in payload
        assert "context" in payload["debug"]
        assert "user" in payload["debug"]["context"]

        # User context should be populated
        user_context = payload["debug"]["context"]["user"]
        assert user_context["id"] == str(test_user_id)
        assert user_context["roles"] == ["admin"]

    finally:
        clear_registration()


def test_user_context_not_included_in_production() -> None:
    """Test that user context is not included in production mode."""
    import uuid

    from flask_more_smorest.perms.user_context import (
        clear_registration,
        register_user_class,
    )

    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = False

    # Set up mock user context
    test_user_id = uuid.uuid4()

    class MockUser:
        id = test_user_id

        def has_role(self, role: str) -> bool:
            return role == "admin"

        def list_roles(self) -> list[str]:
            return ["admin"]

    def get_mock_user():
        return MockUser()

    try:
        with app.app_context():
            register_user_class(MockUser, get_current_user=get_mock_user)
            with app.test_request_context():
                try:
                    raise DummyException("test error")
                except DummyException as exc:
                    response = exc.make_error_response()

        payload = response.get_json()

        # Debug context should NOT be included in production
        assert "debug" not in payload

    finally:
        clear_registration()
