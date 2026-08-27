"""Unit tests for error.integrity and the integrity/database error handlers.

Test strategy:
- Part A: pure-parse tests with synthetic IntegrityError, no real DB.
  Covers both the psycopg/diag branch and the SQLite message branch.
- Part B: to_api_exception mapping tests (kind -> HTTP status / exception class).
  These need an app context so that _humanize_table can reach db.Model.registry.
- Part C: handler-level tests through a real Flask app: wire format of the 422
  response, and sanitisation of database/generic errors outside debug mode.

Values from DETAIL strings must NEVER appear in Violation.columns or in any
response body; assertions confirm this.
"""

import types

import pytest
import sqlalchemy as sa
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.exc import IntegrityError, OperationalError

from flask_more_smorest import db
from flask_more_smorest.error.error_handlers import RequestHandlers
from flask_more_smorest.error.exceptions import DBError, IntegrityConflict, ResourceInUse
from flask_more_smorest.error.integrity import parse_integrity_error, to_api_exception

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_pg_exc(
    sqlstate: str,
    table_name: str | None = None,
    column_name: str | None = None,
    message_detail: str | None = None,
    statement: str = "SELECT 1",
) -> IntegrityError:
    """Return a synthetic psycopg-style IntegrityError with a .diag namespace.

    No real DB connection is needed: we duck-type on ``hasattr(orig, 'diag')``.
    """
    diag = types.SimpleNamespace(
        sqlstate=sqlstate,
        table_name=table_name,
        column_name=column_name,
        message_detail=message_detail,
    )
    orig = types.SimpleNamespace(diag=diag)
    return IntegrityError(statement, {}, orig)  # type: ignore[arg-type]


def make_sqlite_exc(message: str) -> IntegrityError:
    """Return a synthetic SQLite-style IntegrityError (no .diag attribute)."""
    orig = Exception(message)
    return IntegrityError("SELECT 1", {}, orig)


# ---------------------------------------------------------------------------
# A. parse_integrity_error — Postgres (psycopg/diag) branch
# ---------------------------------------------------------------------------


class TestParseIntegrityErrorPostgres:
    """parse_integrity_error with synthetic psycopg-style exceptions."""

    def test_unique_single_column(self) -> None:
        exc = make_pg_exc(
            "23505",
            table_name="vessel",
            message_detail="Key (imo)=(1234567) already exists.",
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "unique"
        assert v.columns == ("imo",)
        assert v.table == "vessel"
        assert v.target_table is None

    def test_unique_composite_key(self) -> None:
        exc = make_pg_exc(
            "23505",
            table_name="contract",
            message_detail="Key (group_id, version)=(abc, 2) already exists.",
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "unique"
        assert v.columns == ("group_id", "version")
        assert v.table == "contract"

    def test_unique_column_names_never_contain_values(self) -> None:
        """Column names extracted from DETAIL must not contain user-supplied values."""
        exc = make_pg_exc(
            "23505",
            table_name="vessel",
            message_detail="Key (mmsi)=(227123456) already exists.",
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.columns == ("mmsi",)
        for col in v.columns:
            assert "227123456" not in col

    def test_fk_missing(self) -> None:
        exc = make_pg_exc(
            "23503",
            table_name="vessel",
            message_detail='Key (flag)=(ZZ) is not present in table "country".',
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "fk_missing"
        assert v.columns == ("flag",)
        assert v.target_table == "country"

    def test_restrict(self) -> None:
        # psycopg reports the table owning the FK constraint (the *referencing*
        # child table) in diag.table_name, not the table being deleted.
        exc = make_pg_exc(
            "23503",
            table_name="vessel",
            message_detail='Key (iso3)=(FRA) is still referenced from table "vessel".',
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "restrict"
        assert v.columns == ("iso3",)
        assert v.target_table == "vessel"

    def test_not_null(self) -> None:
        exc = make_pg_exc("23502", table_name="vessel", column_name="name")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "not_null"
        assert v.columns == ("name",)
        assert v.table == "vessel"

    # -- 23503 statement-verb fallback (DETAIL absent or localised) ----------
    # Postgres provides no structured FK direction: both directions share the
    # SQLSTATE, constraint name, source function and diag.table_name (always
    # the referencing table). Verified empirically against Postgres 16.

    def test_fk_no_detail_insert_falls_back_to_fk_missing(self) -> None:
        exc = make_pg_exc("23503", table_name="child", statement="INSERT INTO child (pid) VALUES (%(pid)s)")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "fk_missing"

    def test_fk_no_detail_delete_falls_back_to_restrict(self) -> None:
        exc = make_pg_exc("23503", table_name="child", statement="DELETE FROM parent WHERE id = %(id)s")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "restrict"

    def test_fk_localised_detail_uses_statement_fallback(self) -> None:
        """A non-English DETAIL (lc_messages) must not break classification."""
        exc = make_pg_exc(
            "23503",
            table_name="child",
            message_detail="La clé (pid)=(ZZ) n’est pas présente dans la table « parent ».",  # noqa: RUF001 — realistic fr_FR locale output
            statement="INSERT INTO child (pid) VALUES (%(pid)s)",
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "fk_missing"

    def test_fk_no_detail_update_on_referencing_table_is_fk_missing(self) -> None:
        """UPDATE on the constraint's own (referencing) table -> missing target."""
        exc = make_pg_exc("23503", table_name="child", statement='UPDATE "child" SET pid = %(pid)s')
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "fk_missing"

    def test_fk_no_detail_update_on_referenced_table_is_restrict(self) -> None:
        """UPDATE on the referenced (parent) table -> blocked by references."""
        exc = make_pg_exc("23503", table_name="child", statement="UPDATE parent SET id = %(id)s")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "restrict"

    def test_fk_no_detail_no_statement_degrades_to_restrict(self) -> None:
        exc = make_pg_exc("23503", table_name="child", statement="")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "restrict"

    def test_check_violation(self) -> None:
        exc = make_pg_exc(
            "23514",
            table_name="vessel",
            message_detail="Key (length)=(-10) fails check constraint.",
        )
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "check"
        assert v.table == "vessel"

    def test_exclusion_violation(self) -> None:
        exc = make_pg_exc("23P01", table_name="booking")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "exclusion"
        assert v.table == "booking"

    def test_unparseable_sqlstate_returns_none(self) -> None:
        """An unknown SQLSTATE (not a recognised constraint code) returns None."""
        exc = make_pg_exc("08001", table_name="vessel")
        assert parse_integrity_error(exc) is None

    def test_no_orig_returns_none(self) -> None:
        """IntegrityError with orig=None returns None gracefully."""
        exc = IntegrityError("SELECT 1", {}, None)  # type: ignore[arg-type]
        assert parse_integrity_error(exc) is None


# ---------------------------------------------------------------------------
# A. parse_integrity_error — SQLite message branch
# ---------------------------------------------------------------------------


class TestParseIntegrityErrorSQLite:
    """parse_integrity_error with synthetic SQLite-style exceptions."""

    def test_unique_single_column(self) -> None:
        exc = make_sqlite_exc("UNIQUE constraint failed: vessel.mmsi")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "unique"
        assert v.columns == ("mmsi",)
        assert v.table == "vessel"

    def test_unique_index_form_yields_no_columns(self) -> None:
        """The index'd message form has no usable column: degrade to empty tree."""
        exc = make_sqlite_exc("UNIQUE constraint failed: index 'ux_vessel_imo'")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "unique"
        assert v.columns == ()
        assert v.table is None

    def test_unique_composite_key(self) -> None:
        """Composite UNIQUE violation: comma-separated t.col pairs."""
        exc = make_sqlite_exc("UNIQUE constraint failed: invite.sender_id, invite.recipient_id")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "unique"
        assert v.columns == ("sender_id", "recipient_id")
        assert v.table == "invite"

    def test_not_null(self) -> None:
        exc = make_sqlite_exc("NOT NULL constraint failed: vessel.name")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "not_null"
        assert v.columns == ("name",)
        assert v.table == "vessel"

    def test_foreign_key_degrades_to_restrict_with_empty_columns(self) -> None:
        """SQLite FK gives no column/table info -> restrict with empty columns."""
        exc = make_sqlite_exc("FOREIGN KEY constraint failed")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "restrict"
        assert v.columns == ()
        assert v.table is None
        assert v.target_table is None

    def test_check_constraint(self) -> None:
        exc = make_sqlite_exc("CHECK constraint failed: vessel_type_check")
        v = parse_integrity_error(exc)
        assert v is not None
        assert v.kind == "check"
        assert v.columns == ()

    def test_garbage_returns_none(self) -> None:
        """Completely unrecognised message -> None (not a crash)."""
        exc = make_sqlite_exc("something completely unexpected")
        assert parse_integrity_error(exc) is None


# ---------------------------------------------------------------------------
# B. to_api_exception — kind -> HTTP status / exception class mapping
#    (needs app context for _humanize_table -> db.Model.registry)
# ---------------------------------------------------------------------------


class TestToApiExceptionMapping:
    """to_api_exception returns the correct ApiException subclass per violation kind."""

    def test_unique_maps_to_integrity_conflict_422(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc(
                "23505",
                table_name="user",
                message_detail="Key (email)=(a@b.c) already exists.",
            )
            result = to_api_exception(exc)
        assert isinstance(result, IntegrityConflict)
        assert result.HTTP_STATUS_CODE == 422
        assert result.fields == {"email": "Another user already uses this value."}

    def test_fk_missing_maps_to_integrity_conflict(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc(
                "23503",
                table_name="vessel",
                message_detail='Key (flag)=(ZZ) is not present in table "country".',
            )
            result = to_api_exception(exc)
        assert isinstance(result, IntegrityConflict)
        assert result.HTTP_STATUS_CODE == 422

    def test_not_null_maps_to_integrity_conflict(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc("23502", table_name="vessel", column_name="name")
            result = to_api_exception(exc)
        assert isinstance(result, IntegrityConflict)
        assert result.HTTP_STATUS_CODE == 422
        assert result.fields == {"name": "This field is required."}
        assert result.message == "Missing required field."

    def test_check_maps_to_integrity_conflict(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc("23514", table_name="vessel")
            result = to_api_exception(exc)
        assert isinstance(result, IntegrityConflict)
        assert result.HTTP_STATUS_CODE == 422

    def test_restrict_maps_to_resource_in_use_409(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc(
                "23503",
                table_name="vessel",
                message_detail='Key (iso3)=(FRA) is still referenced from table "vessel".',
            )
            result = to_api_exception(exc)
        assert isinstance(result, ResourceInUse)
        assert result.HTTP_STATUS_CODE == 409
        # diag.table_name is the referencing table, so the message must not
        # blame a specific resource by name.
        assert result.message.startswith("This record is still referenced")

    def test_exclusion_maps_to_resource_in_use_409(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc("23P01", table_name="booking")
            result = to_api_exception(exc)
        assert isinstance(result, ResourceInUse)
        assert result.HTTP_STATUS_CODE == 409
        # Exclusion fires on inserts/updates: the message must not talk about deletion.
        assert "deleted" not in result.message
        assert "conflicts with an existing record" in result.message

    def test_unparseable_maps_to_db_error_500(self, app: Flask) -> None:
        with app.app_context():
            exc = make_pg_exc("08001")  # connection error — not a constraint code
            result = to_api_exception(exc)
        assert isinstance(result, DBError)
        assert result.HTTP_STATUS_CODE == 500

    def test_empty_columns_unique_stays_422(self, app: Flask) -> None:
        """Unique violation with no parseable DETAIL still returns 422 (not 500)."""
        with app.app_context():
            exc = make_pg_exc("23505", table_name="vessel", message_detail=None)
            result = to_api_exception(exc)
        assert isinstance(result, IntegrityConflict)
        assert result.HTTP_STATUS_CODE == 422
        assert result.fields == {}  # degrade rule: 422 kept, empty field tree

    def test_sqlite_fk_maps_to_resource_in_use(self, app: Flask) -> None:
        """SQLite FK without attribution degrades to restrict -> 409 ResourceInUse."""
        with app.app_context():
            exc = make_sqlite_exc("FOREIGN KEY constraint failed")
            result = to_api_exception(exc)
        assert isinstance(result, ResourceInUse)
        assert result.HTTP_STATUS_CODE == 409

    def test_integrity_conflict_error_code(self) -> None:
        assert IntegrityConflict.error_code() == "integrity_conflict"

    def test_resource_in_use_error_code(self) -> None:
        assert ResourceInUse.error_code() == "resource_in_use"


# ---------------------------------------------------------------------------
# C. Handler wire format and sanitisation through a real Flask app
# ---------------------------------------------------------------------------


class TestIntegrityHandlerWireFormat:
    """A real SQLite unique violation through RequestHandlers produces the 422 contract."""

    @pytest.fixture
    def dup_client(self, unit_app: Flask) -> FlaskClient:
        """unit_app (RequestHandlers registered) with a route committing a duplicate user."""

        @unit_app.route("/dup", methods=["POST"])
        def dup() -> str:
            from flask_more_smorest.perms.models.defaults import User

            db.session.add(User(email="dup@example.com"))
            db.session.commit()
            db.session.add(User(email="dup@example.com"))
            db.session.commit()
            return "unreachable"

        return unit_app.test_client()

    def test_duplicate_returns_422_with_field_tree(self, dup_client: FlaskClient) -> None:
        res = dup_client.post("/dup")
        assert res.status_code == 422
        data = res.get_json()
        assert data["type"].endswith("integrity_conflict")
        assert "email" in data["errors"]["json"]

    def test_no_leak_in_response(self, dup_client: FlaskClient) -> None:
        """The response never contains SQL text or driver parameter dumps."""
        res = dup_client.post("/dup")
        body = res.get_data(as_text=True)
        assert "INSERT INTO" not in body
        assert "[parameters:" not in body
        assert "[SQL" not in body

    def test_no_leak_in_warning_logs(self, dup_client: FlaskClient, caplog: pytest.LogCaptureFixture) -> None:
        """At default log level, integrity logging carries no SQL or values."""
        with caplog.at_level("WARNING", logger="flask_more_smorest.error.error_handlers"):
            dup_client.post("/dup")
        log_text = caplog.text
        assert "Integrity violation" in log_text
        assert "dup@example.com" not in log_text
        assert "INSERT INTO" not in log_text
        assert "[parameters:" not in log_text


class TestSanitisedHandlersOutsideDebug:
    """Outside debug/testing, database and generic errors never echo str(e)."""

    @pytest.fixture
    def prod_client(self) -> FlaskClient:
        """Minimal non-debug, non-testing app with RequestHandlers only."""
        app = Flask(__name__)
        app.config["TESTING"] = False
        RequestHandlers(app)

        @app.route("/db-error")
        def db_error() -> str:
            raise OperationalError(
                "SELECT secret FROM vault",
                {"who": "secret-value"},
                Exception("boom [SQL: SELECT secret FROM vault]"),
            )

        @app.route("/integrity-error")
        def integrity_error() -> str:
            raise sa.exc.IntegrityError(
                "INSERT INTO vessel (mmsi) VALUES (227123456)",
                {"mmsi": "227123456"},
                Exception("UNIQUE constraint failed: vessel.mmsi"),
            )

        @app.route("/generic-error")
        def generic_error() -> str:
            raise ValueError("secret-detail-abc")

        return app.test_client()

    def test_db_error_sanitised(self, prod_client: FlaskClient) -> None:
        res = prod_client.get("/db-error")
        assert res.status_code == 500
        body = res.get_data(as_text=True)
        assert res.get_json()["detail"] == "A database error occurred."
        assert "secret" not in body
        assert "[SQL" not in body

    def test_integrity_error_structured_and_sanitised(self, prod_client: FlaskClient) -> None:
        res = prod_client.get("/integrity-error")
        assert res.status_code == 422
        body = res.get_data(as_text=True)
        assert "227123456" not in body
        assert "INSERT INTO" not in body
        data = res.get_json()
        assert data["errors"]["json"]["mmsi"]

    def test_generic_error_sanitised(self, prod_client: FlaskClient) -> None:
        res = prod_client.get("/generic-error")
        assert res.status_code == 500
        body = res.get_data(as_text=True)
        assert res.get_json()["detail"] == "An internal error occurred."
        assert "secret-detail-abc" not in body
