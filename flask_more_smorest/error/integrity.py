"""Integrity-error parsing and translation.

Converts a SQLAlchemy :class:`~sqlalchemy.exc.IntegrityError` into a structured
:class:`~flask_more_smorest.error.exceptions.ApiException` so that database
constraint violations produce meaningful, safe HTTP responses instead of a raw
500 with the driver's error dump.

The mapping encodes *who has to change*:

* Violations the caller can fix by editing the payload — unique, missing
  foreign-key target, not-null and check violations — become
  :class:`~flask_more_smorest.error.exceptions.IntegrityConflict` (**422**)
  with the standard ``errors: {json: {field: [msg]}}`` tree.
* State conflicts with no field to blame — RESTRICT-blocked deletes and
  exclusion violations — become
  :class:`~flask_more_smorest.error.exceptions.ResourceInUse` (**409**).
* Anything unparseable becomes a sanitised
  :class:`~flask_more_smorest.error.exceptions.DBError` (**500**).

Two database reporting styles are understood:

* **PostgreSQL** (psycopg2/psycopg3): structured ``exc.orig.diag`` diagnostics,
  detected by duck-typing so no driver import is required.
* **SQLite**: message-string parsing, with deterministic degradation where
  SQLite provides no attribution (a foreign-key violation carries no column
  information, so it maps to a generic 409).

Column *names* are extracted from the database diagnostics; the offending
*values* (and the statement/parameters) are never forwarded to responses.

The response copy can be customised by mutating :data:`FIELD_TEMPLATES`,
:data:`DETAIL_OVERRIDES`, :data:`RESTRICT_TEMPLATE` and :data:`EXCLUSION_TEMPLATE`
at application startup.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError

from .exceptions import ApiException, DBError, IntegrityConflict, ResourceInUse

logger = logging.getLogger(__name__)

#: Sanitised message used whenever a database error cannot be safely described.
GENERIC_DB_ERROR_MESSAGE = "A database error occurred."

#: Field-level message templates keyed by violation kind. ``{resource}`` and
#: ``{target}`` are filled with a human-readable name derived from the table.
FIELD_TEMPLATES: dict[str, str] = {
    "unique": "Another {resource} already uses this value.",
    "fk_missing": "Referenced {target} does not exist.",
    "not_null": "This field is required.",
    "check": "Value is not allowed here.",
}

#: Response ``detail`` overrides for kinds whose detail differs from the
#: per-field message. Kinds absent here reuse the field message.
DETAIL_OVERRIDES: dict[str, str] = {"not_null": "Missing required field."}

#: Message for deletes/updates blocked by existing references (RESTRICT). No
#: resource name: Postgres reports the *referencing* table in its diagnostics,
#: so naming it would blame the wrong resource.
RESTRICT_TEMPLATE = "This record is still referenced by other records and cannot be deleted."

#: Message template for exclusion violations (e.g. overlapping ranges), which
#: occur on inserts/updates rather than deletes.
EXCLUSION_TEMPLATE = "This {resource} conflicts with an existing record."


@dataclass(frozen=True)
class Violation:
    """Structured representation of a database integrity constraint violation."""

    kind: Literal["unique", "fk_missing", "restrict", "not_null", "check", "exclusion"]
    columns: tuple[str, ...]  # column names only — never values
    table: str | None
    target_table: str | None  # populated for fk_missing / restrict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches Postgres DETAIL: 'Key (col1, col2)=(val1, val2) already exists.'
# Only the parenthesised column list is extracted, never the value side.
_PG_COLS_RE = re.compile(r"Key \((?P<cols>[^)]+)\)=")

# Matches the table name in Postgres DETAIL, e.g.: 'is not present in table "country"'
_PG_TABLE_RE = re.compile(r'table "(\w+)"')

# Leading DML verb and target table of a statement, e.g. 'INSERT INTO "t" ...',
# 'UPDATE public.t SET ...', 'DELETE FROM t ...'.
_DML_RE = re.compile(
    r'\s*(?P<verb>INSERT|UPDATE|DELETE|MERGE)\b\s*(?:INTO\s+|FROM\s+)?(?P<target>[\w."]+)?', re.IGNORECASE
)


def _parse_pg_columns(message_detail: str | None) -> tuple[str, ...]:
    """Extract column names from a Postgres DETAIL string (never values)."""
    if not message_detail:
        return ()
    m = _PG_COLS_RE.search(message_detail)
    if not m:
        return ()
    raw = m.group("cols")
    return tuple(col.strip().strip('"') for col in raw.split(","))


def _parse_pg_target_table(message_detail: str | None) -> str | None:
    """Extract the referenced table name from a Postgres DETAIL string."""
    if not message_detail:
        return None
    m = _PG_TABLE_RE.search(message_detail)
    return m.group(1) if m else None


def _fk_kind_from_statement(statement: str | None, table_name: str | None) -> Literal["fk_missing", "restrict"]:
    """Classify a 23503 violation from the failing statement.

    Locale-independent fallback for when the DETAIL string is absent or not in
    English (Postgres localises it via ``lc_messages``). Postgres provides no
    structured field for the FK direction: both directions share the SQLSTATE,
    constraint name, source function, and even ``diag.table_name`` (always the
    *referencing* table). The statement itself is the only reliable signal:

    * INSERT/MERGE can only violate the constraint by referencing a missing
      target -> ``fk_missing``.
    * DELETE can only be blocked by existing references -> ``restrict``.
    * UPDATE is ambiguous: updating the referencing table's FK column hits a
      missing target, updating the referenced table's key is blocked by
      references. The statement's target table disambiguates: it equals
      ``diag.table_name`` (the referencing table) only in the first case.

    Defaults to ``restrict`` (a generic 409 state conflict) when the statement
    is unavailable, mirroring the documented SQLite degrade rule.
    """
    m = _DML_RE.match(statement or "")
    if not m:
        return "restrict"
    verb = m.group("verb").upper()
    if verb in ("INSERT", "MERGE"):
        return "fk_missing"
    if verb == "DELETE":
        return "restrict"
    # UPDATE: compare the statement's target table with the constraint's table.
    target = (m.group("target") or "").replace('"', "").split(".")[-1]
    if table_name and target and target == table_name:
        return "fk_missing"
    return "restrict"


def _parse_sqlite(orig_str: str) -> Violation | None:
    """Parse a SQLite constraint error string into a Violation."""
    if orig_str.startswith("UNIQUE constraint failed:"):
        rest = orig_str[len("UNIQUE constraint failed:") :].strip()
        parts = [p.strip() for p in rest.split(",")]
        table: str | None = None
        columns: list[str] = []
        for part in parts:
            if "." in part:
                tbl, col = part.split(".", 1)
                if table is None:
                    table = tbl.strip()
                columns.append(col.strip())
            # Parts without a table qualifier (e.g. "index 'ux_foo'") carry no
            # usable column name; skip them (degrades to an empty field tree).
        return Violation(kind="unique", columns=tuple(columns), table=table, target_table=None)

    if orig_str.startswith("NOT NULL constraint failed:"):
        rest = orig_str[len("NOT NULL constraint failed:") :].strip()
        table = None
        column = rest
        if "." in rest:
            tbl, col = rest.split(".", 1)
            table = tbl.strip()
            column = col.strip()
        cols = (column,) if column else ()
        return Violation(kind="not_null", columns=cols, table=table, target_table=None)

    if orig_str.startswith("FOREIGN KEY constraint failed"):
        # SQLite gives no column or table attribution; degrade deterministically
        # to a state conflict (409) rather than guessing.
        return Violation(kind="restrict", columns=(), table=None, target_table=None)

    if orig_str.startswith("CHECK constraint failed"):
        return Violation(kind="check", columns=(), table=None, target_table=None)

    return None


def _humanize_table(table_name: str | None) -> str:
    """Return a human-readable resource name for a DB table name.

    Looks up the SQLAlchemy mapper registry; falls back to the raw table name,
    then to 'record'. Always returns a non-empty string.
    """
    # inline: avoids the error <-> sqla import cycle (sqla.base_model imports
    # error.exceptions), matching the pattern used in error_handlers.py
    from ..sqla import db
    from ..utils import convert_camel_to_snake

    if table_name is None:
        return "record"
    try:
        # db.Model.registry is a SQLAlchemy DeclarativeRegistry; not visible to
        # pyright through the flask-sqlalchemy stubs, so access via Any.
        model_base: Any = db.Model
        mapper_cls = next(
            (
                m.class_
                for m in model_base.registry.mappers
                if m.local_table is not None and m.local_table.name == table_name
            ),
            None,
        )
        if mapper_cls is not None:
            # CamelCase -> "lower case with spaces"
            return convert_camel_to_snake(mapper_cls.__name__).replace("_", " ")
    except Exception as exc:  # pragma: no cover — defensive, registry available in app context
        logger.debug("Could not resolve model for table %r: %s", table_name, exc)
    return table_name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_integrity_error(exc: IntegrityError) -> Violation | None:
    """Parse a SQLAlchemy IntegrityError into a structured Violation.

    Returns None when the error cannot be attributed to a known constraint kind.
    Duck-types on ``exc.orig.diag`` to detect psycopg2/psycopg3 without importing
    either driver.
    """
    orig = exc.orig
    if orig is None:
        return None

    # -- Postgres path: structured diagnostics (psycopg2 / psycopg3) ---------
    if hasattr(orig, "diag"):
        # Cast to Any: orig is BaseException per SQLAlchemy typing, but the
        # psycopg drivers attach a .diag object invisible to static typing.
        orig_any: Any = orig
        diag = orig_any.diag
        sqlstate: str | None = getattr(diag, "sqlstate", None)
        table_name: str | None = getattr(diag, "table_name", None)
        column_name: str | None = getattr(diag, "column_name", None)
        message_detail: str | None = getattr(diag, "message_detail", None)

        if sqlstate == "23505":  # unique_violation
            return Violation(
                kind="unique",
                columns=_parse_pg_columns(message_detail),
                table=table_name,
                target_table=None,
            )

        if sqlstate == "23503":  # foreign_key_violation — discriminate on DETAIL tail
            detail = message_detail or ""
            kind: Literal["fk_missing", "restrict"]
            if "is not present in table" in detail:
                kind = "fk_missing"
            elif "is still referenced from table" in detail:
                kind = "restrict"
            else:
                # DETAIL absent or localised: fall back to the statement verb.
                kind = _fk_kind_from_statement(exc.statement, table_name)
            return Violation(
                kind=kind,
                columns=_parse_pg_columns(message_detail),
                table=table_name,
                target_table=_parse_pg_target_table(message_detail),
            )

        if sqlstate == "23502":  # not_null_violation
            cols = (column_name,) if column_name else ()
            return Violation(kind="not_null", columns=cols, table=table_name, target_table=None)

        if sqlstate == "23514":  # check_violation
            return Violation(
                kind="check",
                columns=_parse_pg_columns(message_detail),
                table=table_name,
                target_table=None,
            )

        if sqlstate == "23P01":  # exclusion_violation
            return Violation(
                kind="exclusion",
                columns=_parse_pg_columns(message_detail),
                table=table_name,
                target_table=None,
            )

        return None

    # -- SQLite path: message string parsing ---------------------------------
    return _parse_sqlite(str(orig))


def to_api_exception(exc: IntegrityError) -> ApiException:
    """Convert an IntegrityError to an ApiException ready for HTTP response.

    Returns:
        IntegrityConflict (422) for caller-fixable violations (unique,
            fk_missing, not_null, check).
        ResourceInUse (409) for state conflicts (restrict, exclusion).
        DBError (500) with a sanitised message when parsing fails.
    """
    violation = parse_integrity_error(exc)

    if violation is None:
        return DBError(GENERIC_DB_ERROR_MESSAGE)

    resource = _humanize_table(violation.table)
    target = _humanize_table(violation.target_table)

    if violation.kind in FIELD_TEMPLATES:
        field_msg = FIELD_TEMPLATES[violation.kind].format(resource=resource, target=target)
        detail = DETAIL_OVERRIDES.get(violation.kind, field_msg)
        fields = dict.fromkeys(violation.columns, field_msg)
        return IntegrityConflict(fields=fields, message=detail)

    # restrict / exclusion — state conflict, no field to blame.
    if violation.kind == "exclusion":
        return ResourceInUse(message=EXCLUSION_TEMPLATE.format(resource=resource))
    return ResourceInUse(message=RESTRICT_TEMPLATE)
