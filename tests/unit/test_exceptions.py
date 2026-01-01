"""Regression tests for ApiException responses."""

from __future__ import annotations

from http import HTTPStatus

from flask import Flask

from flask_more_smorest.error.exceptions import ApiException, UnauthorizedError


class DummyException(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.BAD_REQUEST


class NoTracebackException(ApiException):
    HTTP_STATUS_CODE = HTTPStatus.INTERNAL_SERVER_ERROR
    INCLUDE_TRACEBACK = False


def test_api_exception_includes_debug_context(app: Flask) -> None:
    with app.app_context():
        try:
            raise DummyException("problem", extra="info")
        except DummyException as exc:
            response = exc.make_error_response()

    payload = response.get_json()["error"]
    assert payload["status_code"] == HTTPStatus.BAD_REQUEST
    assert payload["details"]["extra"] == "info"
    assert payload["debug"]["debug_context"]["extra"] == "info"
    assert "traceback" in payload["debug"]["debug_context"]


def test_api_exception_trims_traceback_when_disabled(app: Flask) -> None:
    with app.app_context():
        try:
            raise NoTracebackException("fail")
        except NoTracebackException as exc:
            response = exc.make_error_response()

    payload = response.get_json()["error"]
    assert "traceback" not in payload["debug"]["debug_context"]


def test_subclass_without_extra_kwargs(app: Flask) -> None:
    with app.app_context():
        response = UnauthorizedError("no token").make_error_response()
    payload = response.get_json()["error"]

    assert payload["debug"]["message"] == "no token"
    assert response.status_code == HTTPStatus.UNAUTHORIZED
