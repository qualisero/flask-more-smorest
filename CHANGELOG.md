# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.15.1] - 2026-08-30

### Fixed

- **Filter schemas no longer inherit write validators.** `generate_filter_schema` cloned
  base-schema fields together with their `validate=` chain (Regexp, Length, Range, custom
  callables), so filtering by a stored value that predates a newly added write-time rule
  returned 422 and made those rows unreachable (e.g. a legacy `imo` that no longer matches a
  later-added format validator). `_clone_field` now clears `validators` on every cloned filter
  field — equality fields and `__from`/`__to`/`__min`/`__max` variants alike. Filtering by an
  arbitrary value is always safe (it simply matches nothing); field-type coercion still applies,
  and the `page`/`page_size` bounds are unaffected.

## [0.15.0] - 2026-08-27

### Added

- **Structured `IntegrityError` handling.** New `error.integrity` module translates database
  constraint violations into meaningful HTTP responses instead of a raw 500: unique /
  missing-FK-target / not-null / check violations return **422** (`IntegrityConflict`) with the
  standard `errors: {json: {field: [msg]}}` tree; RESTRICT-blocked deletes and exclusion
  violations return **409** (`ResourceInUse`); unparseable errors return a sanitised 500.
  PostgreSQL is parsed from the structured `diag` diagnostics (psycopg2/psycopg3 detected by
  duck-typing, no driver import); SQLite from its message strings, with deterministic
  degradation where SQLite provides no attribution. Column *names* are extracted, never values.
  Foreign-key direction (missing target vs blocked delete) is discriminated on the `DETAIL`
  string with a locale-independent statement-verb fallback, since Postgres provides no
  structured field for it. `RequestHandlers` registers the handler automatically; message copy
  is customisable via `FIELD_TEMPLATES` / `DETAIL_OVERRIDES` / `RESTRICT_TEMPLATE` /
  `EXCLUSION_TEMPLATE`.

### Fixed

- **Database and generic error responses no longer leak internals outside debug/testing.**
  `handle_db_exception` previously put the driver's error text — including the SQL statement
  and every bound parameter value — into the response `detail`, and `handle_generic_exception`
  echoed `str(e)`. Both are now gated on debug/testing mode and return a generic message in
  production. Database errors are also logged (`exception` level, without duplicating the
  driver text in the message) and integrity violations are logged at `warning` as a value-free
  structured summary (kind/table/columns) — full driver detail only at `debug` — since they are
  expected outcomes of user input and must not push request values into production logs.

## [0.14.0] - 2026-08-15

### Fixed

- **POST endpoints now honour `arg_schema`.** `MethodConfig["arg_schema"]` was documented for
  `POST` but only implemented for `PATCH`: the configured input schema was ignored and the
  response schema was used for the request body as well. `arg_schema` now sets the request body
  schema while `schema` stays the response schema. Fields the model does not define, such as the
  invite code in the invite-only signup example, are validated and then dropped rather than passed
  to the model constructor.

- **POST with a plain (non model-bound) schema now creates the resource.** The handler assumed the
  deserialised payload was a model instance, so with a plain `marshmallow.Schema` it wrote a key
  into the payload dict and returned 200 without persisting anything.

- **Performance monitoring settings are resolved per application.** The SQLAlchemy event hooks are
  registered once on the `Engine` class but captured `SQLALCHEMY_SLOW_QUERY_THRESHOLD` and the
  logging flags from whichever app registered first. Later apps silently inherited that
  configuration, and an app that never enabled `SQLALCHEMY_PERFORMANCE_MONITORING` was still
  monitored and still had its queries counted. Each query now reads the configuration of the app
  that issued it.

### Changed

- **`BaseRoleEnum` is now an `enum.StrEnum`** instead of `(str, enum.Enum)`. Comparisons, `.value`
  and JSON serialisation are unchanged, and stored values are unchanged, but `str(role)`,
  f-strings and `%s` now produce `ADMIN` instead of `BaseRoleEnum.ADMIN`. Check any log line, URL
  fragment or template that interpolates a role directly.

- **`ApiException.get_debug_context` is annotated as `DebugContext`**, a recursive alias for the
  JSON-shaped structure it already returned. Runtime behaviour is unchanged.

### Removed

- **Bandit.** It had five configuration sources, three of which were dead, and reported no issues.
  Ruff's `S` ruleset already covers `flask_more_smorest` and `tests` and remains the security lint.

- **mypy.** Pyright is now the only type checker, with `reportMissingParameterType`,
  `reportMissingTypeArgument` and `reportUnnecessaryTypeIgnoreComment` enabled.

- **The Codecov upload step.** It required an account token that this project does not
  have, so every upload failed with `Token required - not valid tokenless upload` while
  `fail_ci_if_error: false` hid it. Coverage is still reported in the CI test log.

- **The `stubs/` tree.** The package ships `py.typed` and the stubs were never shipped, never
  consulted (`stubPath` pointed at a directory that does not exist) and had drifted from the
  source they duplicated.

## [0.13.1] - 2026-08-12

### Fixed

- **`generate_filter_schema` no longer inherits `Meta.fields` / `Meta.exclude` from the
  response schema.** When a response schema used a `Meta.fields` allowlist, the generated filter
  schema silently dropped `page`, `page_size` and `nulls_match`, causing those endpoints to reject
  `page_size` with 422 and to stop advertising pagination controls in the OpenAPI spec. The filter
  schema now states its own field set explicitly, overriding `fields`, `additional` and `exclude`
  inherited from the response `Meta`.

## [0.13.0] - 2026-07-21

### Added

- **`nulls_match` query parameter** on all auto-generated index filter schemas:
  When `nulls_match=true`, every produced filter condition is widened to
  `(condition OR column IS NULL)`, so records with a null value in that column
  are treated as matching candidates. Applies uniformly to equality, `__from`/
  `__to`, and `__min`/`__max` filters. Default `false` preserves exact
  pre-existing behaviour.

## [0.12.0] - 2026-03-15

### Added

- **`default_page_size` parameter** on `CRUDBlueprint.__init__()`:
  Controls the default page size for INDEX endpoints (default: 20).
  Set to `None` to disable pagination entirely on a blueprint.

- **`page_size=0` means "return all"**: Requesting `page_size=0` in query
  parameters now returns all results without limit/offset. Previously
  rejected as invalid.

### Changed

- Default page size changed from 10 to 20.
- Marshmallow `page_size` validator now allows `min=0` (was `min=1`).

### Fixed

- Error handler registration in `Api.init_app()` now properly catches
  `ApiException` subclasses (`ForbiddenError`, `UnauthorizedError`, etc.)
  and returns structured HTTP error responses instead of falling through
  to Flask's default 500 handler.

## [0.11.0] - 2026-02-23

### Added

- **`strip_suffixes()` for class name normalisation** (`blueprint_operationid`):
  Strips `View`, `MethodView`, `Index`, `List`, `Collection`, `V1`/`V2` etc.
  from class names before building the operationId. `UserListView` on `GET /users/`
  → `listUsers` (instead of `listUserListView`).

- **Inflect-based pluralisation** (`blueprint_operationid`):
  Collection endpoints (trailing-slash or `many=True`) now produce properly pluralised
  operationIds (`listUsers`, `listProjects`, `listNews`).  Handles irregular plurals,
  already-plural words, and compound `FooByBar` names
  (`AppointmentByRef` → `listAppointmentsByRef`).  Adds `inflect ≥ 7.5` as a runtime
  dependency.

- **`many=True` collection detection** (`blueprint_operationid`):
  A GET endpoint whose `@bp.response()` decorator carries a schema with `many=True` is
  now treated as a collection endpoint (`listXxx`) even when the path has no trailing
  slash.

- **`operation_id`, `operation_id_prefix`, `operation_id_suffix` on `route()`**:
  Three new keyword arguments allow per-route customisation:
  - `operation_id="myId"` — explicit full operationId for a function-based route.
  - `operation_id_prefix="_deprecated_"` — prefix prepended to every auto-generated
    operationId on a MethodView (useful for deprecation markers).
  - `operation_id_suffix="_v2"` — suffix appended to every auto-generated operationId
    on a MethodView (useful for API versioning).

### Changed
- **`BlueprintOperationIdMixin` architecture** (`blueprint_operationid`):
  operationId injection is now performed inside the `_store_endpoint_docs` hook (after
  all decorators have accumulated their metadata) rather than via `self.doc()` at
  decoration time.  This makes the injection order-independent with respect to other
  Flask-Smorest decorators and enables per-rule customisation for the same MethodView
  registered at multiple routes.

### Breaking Changes
- **`PUT` now maps to `"set"` prefix** in `HTTP_METHOD_OPERATION_MAP` (was `"replace"`).
  A `PUT /item/<id>` endpoint on `class Item(MethodView)` now generates `setItem`
  instead of `replaceItem`.  Update any code that relied on the old `replace` prefix.

## [0.10.0] - 2026-01-26

### Added
- **User Registry System**: Centralized registry for user model registration
  - `init_fms(user, role, token, domain, setting)` - Single entry point for model registration
  - `get_user_model()`, `get_role_model()`, `get_token_model()`, `get_domain_model()`, `get_setting_model()` - Runtime model access
