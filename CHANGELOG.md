# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
