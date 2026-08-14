"""Tests for SQLAlchemy performance monitoring hooks."""

from __future__ import annotations

import logging
from collections.abc import Generator
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from flask import Flask

from flask_more_smorest import db, init_db
from flask_more_smorest.sqla import database as database_module
from flask_more_smorest.sqla.database import get_request_query_stats


@pytest.fixture(autouse=True)
def reset_performance_hooks():
    """Reset the performance hooks registration flag before each test."""
    database_module._performance_hooks_registered = False
    yield
    database_module._performance_hooks_registered = False


@pytest.fixture
def app_with_monitoring() -> Generator[Flask, None, None]:
    """Create a Flask app with performance monitoring enabled."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_PERFORMANCE_MONITORING"] = True
    app.config["SQLALCHEMY_SLOW_QUERY_THRESHOLD"] = 0.001  # Very low for testing

    init_db(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app_without_monitoring() -> Generator[Flask, None, None]:
    """Create a Flask app without performance monitoring."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    # Performance monitoring is off by default

    init_db(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.mark.usefixtures("app_with_monitoring")
class TestPerformanceMonitoringEnabled:
    """Tests for performance monitoring enabled behavior."""

    def test_performance_monitoring_logs_slow_queries(
        self, app_with_monitoring: Flask, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that slow queries are logged when they exceed threshold."""
        import time

        # Patch time.perf_counter to simulate a slow query
        original_perf_counter = time.perf_counter
        call_count = [0]

        def mock_perf_counter() -> float:
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                # Second call (after query): return 10 seconds later
                return original_perf_counter() + 10.0
            return original_perf_counter()

        with patch("time.perf_counter", side_effect=mock_perf_counter):
            with caplog.at_level(logging.WARNING):
                db.session.execute(sa.text("SELECT 1"))

        # Check that slow query was logged
        assert any("Slow query detected" in record.message for record in caplog.records)

    def test_performance_monitoring_tracks_request_stats(self) -> None:
        """Test that query statistics are tracked per request."""
        # Execute some queries
        db.session.execute(sa.text("SELECT 1"))
        db.session.execute(sa.text("SELECT 2"))
        db.session.execute(sa.text("SELECT 3"))

        stats = get_request_query_stats()

        assert stats["query_count"] >= 3
        assert stats["total_query_time"] > 0

    def test_query_count_accumulates_within_request(self) -> None:
        """Test that query counts accumulate within a request."""
        # Get initial count
        initial_stats = get_request_query_stats()
        initial_count = initial_stats["query_count"]

        # Execute queries
        db.session.execute(sa.text("SELECT 1"))
        db.session.execute(sa.text("SELECT 2"))

        # Check counts increased
        final_stats = get_request_query_stats()
        assert final_stats["query_count"] >= initial_count + 2
        assert final_stats["total_query_time"] > 0


def test_get_request_query_stats_without_context() -> None:
    """Test that get_request_query_stats returns zeros outside request context."""
    # Outside app context
    stats = get_request_query_stats()

    assert stats["query_count"] == 0
    assert stats["total_query_time"] == 0.0


@pytest.mark.usefixtures("app_without_monitoring")
class TestPerformanceMonitoringDisabled:
    """Tests for performance monitoring disabled behavior."""

    def test_performance_monitoring_disabled_by_default(
        self, app_without_monitoring: Flask, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that performance monitoring is disabled by default."""
        with caplog.at_level(logging.DEBUG):
            db.session.execute(sa.text("SELECT 1"))

        # No slow query log (monitoring disabled)
        assert not any("Slow query detected" in record.message for record in caplog.records)


class TestPerformanceMonitoringConfig:
    """Tests for performance monitoring configuration options."""

    def test_performance_monitoring_logs_info_on_enable(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that enabling monitoring logs an info message."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_PERFORMANCE_MONITORING"] = True

        with caplog.at_level(logging.INFO):
            init_db(app)

    def test_slow_query_threshold_configurable(self) -> None:
        """Test that slow query threshold can be configured."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_PERFORMANCE_MONITORING"] = True
        app.config["SQLALCHEMY_SLOW_QUERY_THRESHOLD"] = 5.0  # 5 seconds

        init_db(app)

        with app.app_context():
            db.create_all()

            # With a 5 second threshold, normal queries won't be logged as slow
            with patch.object(logging.getLogger("flask_more_smorest.sqla.database"), "warning") as mock_warning:
                db.session.execute(sa.text("SELECT 1"))
                # Should not be called since query is faster than 5s
                mock_warning.assert_not_called()

            db.session.remove()
            db.drop_all()

    def test_log_all_queries_option(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that SQLALCHEMY_LOG_ALL_QUERIES logs queries at DEBUG level."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_PERFORMANCE_MONITORING"] = True
        app.config["SQLALCHEMY_LOG_ALL_QUERIES"] = True
        app.config["SQLALCHEMY_SLOW_QUERY_THRESHOLD"] = 100.0  # High threshold so queries won't be "slow"

        init_db(app)

        with app.app_context():
            db.create_all()

            with caplog.at_level(logging.DEBUG):
                db.session.execute(sa.text("SELECT 1"))

            # Check that query was logged at DEBUG level
            debug_messages = [record.message for record in caplog.records if record.levelname == "DEBUG"]
            assert any("Query executed" in msg for msg in debug_messages)

            db.session.remove()
            db.drop_all()

    def test_parameter_logging_can_be_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that query parameter logging can be disabled for security."""
        import time

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_PERFORMANCE_MONITORING"] = True
        app.config["SQLALCHEMY_SLOW_QUERY_THRESHOLD"] = 0.001  # Very low threshold
        app.config["SQLALCHEMY_LOG_QUERY_PARAMETERS"] = False  # Disable parameter logging

        init_db(app)

        with app.app_context():
            db.create_all()

            # Patch time.perf_counter to simulate a slow query
            original_perf_counter = time.perf_counter
            call_count = [0]

            def mock_perf_counter() -> float:
                call_count[0] += 1
                if call_count[0] % 2 == 0:
                    return original_perf_counter() + 10.0
                return original_perf_counter()

            with patch("time.perf_counter", side_effect=mock_perf_counter):
                with caplog.at_level(logging.WARNING):
                    db.session.execute(sa.text("SELECT 1"))

            # Check that slow query was logged but without parameters
            slow_query_records = [r for r in caplog.records if "Slow query detected" in r.message]
            assert len(slow_query_records) > 0
            # Parameters should not be in the extra data
            for record in slow_query_records:
                if hasattr(record, "parameters"):
                    assert record.parameters is None or "parameters" not in record.__dict__

            db.session.remove()
            db.drop_all()


class TestPerformanceMonitoringPerApp:
    """The Engine hooks are global, so each query must read its own app's config."""

    def _make_app(self, **config: object) -> Flask:
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config.update(config)
        init_db(app)
        return app

    def test_second_app_is_not_bound_to_the_first_apps_threshold(self) -> None:
        """A low threshold registered by one app must not leak into another."""
        noisy = self._make_app(
            SQLALCHEMY_PERFORMANCE_MONITORING=True,
            SQLALCHEMY_SLOW_QUERY_THRESHOLD=0.0,
        )
        quiet = self._make_app(
            SQLALCHEMY_PERFORMANCE_MONITORING=True,
            SQLALCHEMY_SLOW_QUERY_THRESHOLD=5.0,
        )
        db_logger = logging.getLogger("flask_more_smorest.sqla.database")

        with noisy.app_context():
            db.create_all()
            with patch.object(db_logger, "warning") as mock_warning:
                db.session.execute(sa.text("SELECT 1"))
                mock_warning.assert_called()
            db.session.remove()
            db.drop_all()

        with quiet.app_context():
            db.create_all()
            with patch.object(db_logger, "warning") as mock_warning:
                db.session.execute(sa.text("SELECT 1"))
                mock_warning.assert_not_called()
            db.session.remove()
            db.drop_all()

    def test_app_without_monitoring_is_never_monitored(self) -> None:
        """Hooks registered by another app must stay inert for an opted-out app."""
        self._make_app(SQLALCHEMY_PERFORMANCE_MONITORING=True, SQLALCHEMY_SLOW_QUERY_THRESHOLD=0.0)
        plain = self._make_app()

        with plain.app_context():
            db.create_all()
            with patch.object(logging.getLogger("flask_more_smorest.sqla.database"), "warning") as mock_warning:
                db.session.execute(sa.text("SELECT 1"))
                mock_warning.assert_not_called()
            assert get_request_query_stats()["query_count"] == 0
            db.session.remove()
            db.drop_all()
