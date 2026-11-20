"""Integration tests for INDEX route permission enforcement (plan §4).

Covers:
  1. SQL path - UserOwnershipMixin: owners A/B/admin see only their rows; anonymous -> [].
  2. Fallback path - _can_read only: same matrix; pagination correctness.
  3. bypass_perms() context manager lists every row.
  4. Nested route combines URL path kwargs with the SQL criterion.
  5. Existing test_crud_integration.py still passes (plain BaseModel, unaffected).
"""

from __future__ import annotations

import contextlib
import json
import sys
import types
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy.orm import Mapped, mapped_column

from flask_more_smorest import Api, CRUDBlueprint, CRUDMethod, db, init_db, init_jwt
from flask_more_smorest.perms import BasePermsModel, UserOwnershipMixin, clear_registration, init_fms
from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.perms.models.base_roles import BaseRoleEnum

if TYPE_CHECKING:
    from flask_sqlalchemy.session import Session
    from sqlalchemy.orm import scoped_session

# ---------------------------------------------------------------------------
# Module-level placeholders; replaced by _load_models fixture.
# ---------------------------------------------------------------------------
NoteModel: type[BasePermsModel] = BasePermsModel
TagModel: type[BasePermsModel] = BasePermsModel
AdminGatedModel: type[BasePermsModel] = BasePermsModel
OverrideNoteModel: type[BasePermsModel] = BasePermsModel


@pytest.fixture(scope="module", autouse=True)
def _load_models() -> Iterator[None]:
    global NoteModel, TagModel, AdminGatedModel, OverrideNoteModel

    clear_registration()
    db.metadata.clear()

    class Note(UserOwnershipMixin, BasePermsModel):
        """SQL-path model: UserOwnershipMixin supplies _readable_filter."""

        __module__ = __name__
        __tablename__ = "idx_note"

        body: Mapped[str] = mapped_column(sa.String(200), nullable=False)

    class Tag(BasePermsModel):
        """Fallback-path model: custom _can_read, no _readable_filter."""

        __module__ = __name__
        __tablename__ = "idx_tag"

        label: Mapped[str] = mapped_column(sa.String(100), nullable=False)

        def _can_read(self, user: Any) -> bool:
            # Readable when authenticated @ok.test AND row label does not start with "hidden"
            return user is not None and user.email.endswith("@ok.test") and not self.label.startswith("hidden")

        def _can_write(self, user: Any) -> bool:
            return user is not None

    class AdminGated(BasePermsModel):
        """Fix 4: has is_admin column, _can_read self-only; admin sees non-is_admin rows via per-row check."""

        __module__ = __name__
        __tablename__ = "idx_admin_gated"

        name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
        is_admin: Mapped[bool] = mapped_column(sa.Boolean(), default=False, nullable=False)
        owner_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False)

        def _can_read(self, user: Any) -> bool:
            return bool(user) and self.owner_id == user.id

        def _can_write(self, user: Any) -> bool:
            return bool(user) and self.owner_id == user.id

    class OverrideNote(UserOwnershipMixin, BasePermsModel):
        """Fix 5: UserOwnershipMixin with _can_read overridden; _readable_filter returns None → per-row fallback."""

        __module__ = __name__
        __tablename__ = "idx_override_note"

        body: Mapped[str] = mapped_column(sa.String(200), nullable=False)

        def _can_read(self, user: Any) -> bool:
            return False  # always deny; tests that _can_read override disables SQL filter

    NoteModel = Note
    TagModel = Tag
    AdminGatedModel = AdminGated
    OverrideNoteModel = OverrideNote

    # Inject into sys.modules so CRUDBlueprint can import by name string.
    _note_mod = types.ModuleType("_idx_note_mod")
    _note_mod.Note = Note
    sys.modules["_idx_note_mod"] = _note_mod

    _tag_mod = types.ModuleType("_idx_tag_mod")
    _tag_mod.Tag = Tag
    sys.modules["_idx_tag_mod"] = _tag_mod

    _admin_gated_mod = types.ModuleType("_idx_admin_gated_mod")
    _admin_gated_mod.AdminGated = AdminGated
    sys.modules["_idx_admin_gated_mod"] = _admin_gated_mod

    _override_note_mod = types.ModuleType("_idx_override_note_mod")
    _override_note_mod.OverrideNote = OverrideNote
    sys.modules["_idx_override_note_mod"] = _override_note_mod

    yield

    clear_registration()
    db.metadata.clear()
    with contextlib.suppress(Exception):
        sa.orm.clear_mappers()
    for mod in (
        "_idx_note_mod",
        "_idx_tag_mod",
        "_idx_admin_gated_mod",
        "_idx_override_note_mod",
        "flask_more_smorest.perms.user_schemas",
    ):
        sys.modules.pop(mod, None)


# ---------------------------------------------------------------------------
# App, DB, users, tokens
# ---------------------------------------------------------------------------


@pytest.fixture
def perms_index_app(_load_models: None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        API_TITLE="Index Perms Test",
        API_VERSION="v1",
        OPENAPI_VERSION="3.0.2",
        SECRET_KEY="idx-test-secret",
        JWT_SECRET_KEY="idx-jwt-secret",
    )

    dm = defaults_module
    init_fms(user=dm.User, role=dm.UserRole, token=dm.Token, domain=dm.Domain, setting=dm.UserSetting)
    init_db(app)
    init_jwt(app)

    api = Api(app)

    # Case 1 & 3: SQL-path blueprint with public INDEX.
    notes_bp = CRUDBlueprint(
        "notes",
        __name__,
        model="Note",
        model_import_name="_idx_note_mod",
        schema_import_name="_idx_note_mod",
        url_prefix="/notes/",
        methods={
            CRUDMethod.INDEX: {"public": True},
            CRUDMethod.GET: True,
            CRUDMethod.POST: True,
        },
    )
    api.register_blueprint(notes_bp)

    # Case 2: Fallback-path blueprint with public INDEX and page_size=1.
    tags_bp = CRUDBlueprint(
        "tags",
        __name__,
        model="Tag",
        model_import_name="_idx_tag_mod",
        schema_import_name="_idx_tag_mod",
        url_prefix="/tags/",
        default_page_size=1,
        methods={
            CRUDMethod.INDEX: {"public": True},
            CRUDMethod.GET: True,
            CRUDMethod.POST: True,
        },
    )
    api.register_blueprint(tags_bp)

    # Case 4: Nested blueprint - URL path injects user_id into filter_by(**kwargs).
    nested_notes_bp = CRUDBlueprint(
        "user_notes",
        __name__,
        model="Note",
        model_import_name="_idx_note_mod",
        schema_import_name="_idx_note_mod",
        url_prefix="/users/<uuid:user_id>/notes/",
        methods={CRUDMethod.INDEX: True},
    )
    api.register_blueprint(nested_notes_bp)

    # Fix 4: AdminGated blueprint - authenticated INDEX on a model with is_admin column.
    admin_gated_bp = CRUDBlueprint(
        "admin_gated",
        __name__,
        model="AdminGated",
        model_import_name="_idx_admin_gated_mod",
        schema_import_name="_idx_admin_gated_mod",
        url_prefix="/admin_gated/",
        methods={CRUDMethod.INDEX: True},
    )
    api.register_blueprint(admin_gated_bp)

    # Fix 5: OverrideNote blueprint - UserOwnershipMixin with overridden _can_read.
    override_notes_bp = CRUDBlueprint(
        "override_notes",
        __name__,
        model="OverrideNote",
        model_import_name="_idx_override_note_mod",
        schema_import_name="_idx_override_note_mod",
        url_prefix="/override_notes/",
        methods={CRUDMethod.INDEX: True},
    )
    api.register_blueprint(override_notes_bp)

    return app


@pytest.fixture
def db_session(perms_index_app: Flask) -> Iterator[scoped_session[Session]]:
    with perms_index_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def users(
    perms_index_app: Flask,
    db_session: scoped_session[Session],
) -> dict[str, Any]:
    dm = defaults_module
    with NoteModel.bypass_perms():
        domain = dm.Domain(name="idx_domain", display_name="Idx Domain")
        db_session.add(domain)
        db_session.commit()

        user_a = dm.User(email="a@ok.test", password="pw")
        user_b = dm.User(email="b@ok.test", password="pw")
        admin = dm.User(email="admin@example.com", password="pw")
        for u in (user_a, user_b, admin):
            db_session.add(u)
        db_session.commit()

        for u, role in (
            (user_a, BaseRoleEnum.USER),
            (user_b, BaseRoleEnum.USER),
            (admin, BaseRoleEnum.ADMIN),
        ):
            db_session.add(dm.UserRole(user_id=u.id, role=role, domain_id=domain.id))
        db_session.commit()

    return {"a": user_a, "b": user_b, "admin": admin}


@pytest.fixture
def tokens(
    perms_index_app: Flask,
    db_session: scoped_session[Session],
    users: dict[str, Any],
) -> dict[str, str]:
    return {
        "a": create_access_token(identity=users["a"].id),
        "b": create_access_token(identity=users["b"].id),
        "admin": create_access_token(identity=users["admin"].id),
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Case 1: SQL path (UserOwnershipMixin._readable_filter → WHERE user_id == user.id)
# ---------------------------------------------------------------------------


class TestSQLPath:
    """Notes blueprint uses UserOwnershipMixin SQL criterion; count is exact without loading all rows."""

    def _create_notes(self, db_session: scoped_session[Session], users: dict[str, Any]) -> None:
        with NoteModel.bypass_perms():
            for body in ("a1", "a2"):
                db_session.add(NoteModel(body=body, user_id=users["a"].id))
            db_session.add(NoteModel(body="b1", user_id=users["b"].id))
            db_session.commit()

    @pytest.mark.parametrize(
        ("token_key", "expected_count"),
        [("a", 2), ("b", 1)],
    )
    def test_owner_sees_only_own_rows(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
        token_key: str,
        expected_count: int,
    ) -> None:
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get("/notes/", headers=_auth(tokens[token_key]))
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == expected_count
        assert all(r["user_id"] == str(users[token_key].id) for r in data)

    def test_admin_sees_all_rows(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get("/notes/", headers=_auth(tokens["admin"]))
        assert resp.status_code == 200
        assert len(resp.get_json()) == 3

    def test_anonymous_public_index_empty(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """Public INDEX: anonymous user → _readable_filter(None) returns sa.false() → []."""
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get("/notes/")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Case 2: Fallback path (_can_read only, Python per-row filter)
# ---------------------------------------------------------------------------


class TestFallbackPath:
    """Tag blueprint has no _readable_filter; index falls back to Python can_read() per row."""

    def _create_tags(self, db_session: scoped_session[Session]) -> list[str]:
        with TagModel.bypass_perms():
            tags = [TagModel(label=lbl) for lbl in ("hidden0", "tag1", "hidden2", "tag3")]
            for t in tags:
                db_session.add(t)
            db_session.commit()
            return [str(t.id) for t in tags]

    @pytest.mark.parametrize("token_key", ["a", "b"])
    def test_ok_user_sees_all_rows_paginated(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
        token_key: str,
    ) -> None:
        """@ok.test user reads non-hidden rows; with page_size=1 total==2, page 1 has 1 item."""
        self._create_tags(db_session)
        resp = perms_index_app.test_client().get(
            "/tags/",
            query_string={"page": 1, "page_size": 1},
            headers=_auth(tokens[token_key]),
        )
        assert resp.status_code == 200
        pag = json.loads(resp.headers["X-Pagination"])
        assert pag["total"] == 2
        assert len(resp.get_json()) == 1

    @pytest.mark.parametrize("token_key", ["a", "b"])
    def test_page2_returns_second_readable_row(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
        token_key: str,
    ) -> None:
        tag_ids = self._create_tags(db_session)
        resp = perms_index_app.test_client().get(
            "/tags/",
            query_string={"page": 2, "page_size": 1},
            headers=_auth(tokens[token_key]),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == tag_ids[3]  # second readable row: "tag3" (index 3)

    def test_admin_bypasses_per_row_check(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        self._create_tags(db_session)
        resp = perms_index_app.test_client().get(
            "/tags/",
            query_string={"page": 1, "page_size": 10},
            headers=_auth(tokens["admin"]),
        )
        assert resp.status_code == 200
        pag = json.loads(resp.headers["X-Pagination"])
        assert pag["total"] == 4

    def test_anonymous_public_index_empty(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """Public INDEX: anonymous user → can_read(None) → False for all rows → []."""
        self._create_tags(db_session)
        resp = perms_index_app.test_client().get("/tags/")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Case 3: bypass_perms lists every row regardless of perms
# ---------------------------------------------------------------------------


class TestBypassPerms:
    def test_bypass_perms_disables_sql_criterion(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """bypass_perms() sets perms_disabled; _user_bypasses_perms returns True → no WHERE clause."""
        with NoteModel.bypass_perms():
            db_session.add(NoteModel(body="a-note", user_id=users["a"].id))
            db_session.add(NoteModel(body="b-note", user_id=users["b"].id))
            db_session.commit()

        client = perms_index_app.test_client()

        # Normal request as user_a: only 1 row (SQL criterion filters to owner)
        resp_normal = client.get("/notes/", headers=_auth(tokens["a"]))
        assert len(resp_normal.get_json()) == 1

        # bypass_perms: perms_disabled=True → all rows returned
        with NoteModel.bypass_perms():
            resp_bypass = client.get("/notes/", headers=_auth(tokens["a"]))
        assert len(resp_bypass.get_json()) == 2


# ---------------------------------------------------------------------------
# Case 4: Path-filtered nested list - kwargs + SQL criterion combined
# ---------------------------------------------------------------------------


class TestNestedPath:
    """Nested route /users/<uuid:user_id>/notes/ applies filter_by(user_id=…) AND the SQL criterion."""

    def _create_notes(self, db_session: scoped_session[Session], users: dict[str, Any]) -> None:
        with NoteModel.bypass_perms():
            for body in ("a1", "a2"):
                db_session.add(NoteModel(body=body, user_id=users["a"].id))
            db_session.add(NoteModel(body="b1", user_id=users["b"].id))
            db_session.commit()

    def test_own_nested_list_returns_own_rows(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """user_a requests /users/<a_id>/notes/ → filter_by(user_id=A) ∧ user_id==A → 2 rows."""
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get(
            f"/users/{users['a'].id}/notes/",
            headers=_auth(tokens["a"]),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert all(r["user_id"] == str(users["a"].id) for r in data)

    def test_cross_user_nested_list_empty(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """user_b requests /users/<a_id>/notes/ → filter_by(user_id=A) ∧ user_id==B → 0 rows."""
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get(
            f"/users/{users['a'].id}/notes/",
            headers=_auth(tokens["b"]),
        )
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_own_path_own_notes(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """user_b requests /users/<b_id>/notes/ → 1 row."""
        self._create_notes(db_session, users)
        resp = perms_index_app.test_client().get(
            f"/users/{users['b'].id}/notes/",
            headers=_auth(tokens["b"]),
        )
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1


# ---------------------------------------------------------------------------
# Fix 4: is_admin guard - admin index uses per-row can_read()
# ---------------------------------------------------------------------------


class TestIsAdminPerRow:
    """INDEX on a model with is_admin column: admin user triggers per-row check so is_admin=True rows are excluded."""

    def _create_rows(self, db_session: scoped_session[Session], users: dict[str, Any]) -> None:
        with AdminGatedModel.bypass_perms():
            db_session.add(AdminGatedModel(name="normal", is_admin=False, owner_id=users["a"].id))
            db_session.add(AdminGatedModel(name="is-admin", is_admin=True, owner_id=users["a"].id))
            db_session.commit()

    def test_admin_excludes_is_admin_true_rows(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """Admin lists AdminGated: is_admin=True row blocked by _check_admin_bypass guard → absent."""
        self._create_rows(db_session, users)
        resp = perms_index_app.test_client().get("/admin_gated/", headers=_auth(tokens["admin"]))
        assert resp.status_code == 200
        data = resp.get_json()
        names = [r["name"] for r in data]
        assert "normal" in names
        assert "is-admin" not in names


# ---------------------------------------------------------------------------
# Fix 5: UserOwnershipMixin with overridden _can_read falls back to per-row
# ---------------------------------------------------------------------------


class TestOwnershipOverride:
    """UserOwnershipMixin._readable_filter returns None when _can_read is overridden; per-row fallback."""

    def test_owner_gets_empty_list(
        self,
        perms_index_app: Flask,
        db_session: scoped_session[Session],
        users: dict[str, Any],
        tokens: dict[str, str],
    ) -> None:
        """OverrideNote._readable_filter returns None (override detected); per-row can_read() denies all → []."""
        with OverrideNoteModel.bypass_perms():
            db_session.add(OverrideNoteModel(body="secret", user_id=users["a"].id))
            db_session.commit()
        resp = perms_index_app.test_client().get("/override_notes/", headers=_auth(tokens["a"]))
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# User models: default User keeps the SQL filter; a _can_read override falls back
# ---------------------------------------------------------------------------


class TestUserReadableFilter:
    def test_default_user_has_sql_filter(self, users: dict[str, Any]) -> None:
        criterion = defaults_module.User._readable_filter(users["a"])
        assert criterion is not None
        assert str(criterion) == str(defaults_module.User.id == users["a"].id)

    def test_overridden_can_read_falls_back(self, users: dict[str, Any]) -> None:
        class CustomUser(defaults_module.User):
            __abstract__ = True

            def _can_read(self, user: Any) -> bool:
                return True

        assert CustomUser._readable_filter(users["a"]) is None
