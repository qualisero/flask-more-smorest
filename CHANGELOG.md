# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.2] - 2026-01-22

### Added
- **Polymorphic Inheritance Support**: Core models now support SQLAlchemy polymorphic inheritance
  - Added `discriminator` column to `Token` model with default `"token"`
  - Added `discriminator` column to `UserSetting` model with default `"user_setting"`
  - Added `__mapper_args__` with `polymorphic_on` and `polymorphic_identity` to both models
  - Enables applications to subclass these models with custom fields while maintaining ORM relationships
  - Includes comprehensive documentation and examples in model docstrings

- **Domain/Tenant Nomenclature Aliases**: Added backward-compatible aliases for multi-tenant exceptions
  - `NoDomainAccessError` as alias for `NoTenantAccessError`
  - `DomainNotFoundError` as alias for `TenantNotFoundError`
  - Allows applications to use either "domain" or "tenant" terminology consistently

- **Enhanced User.has_domain_access()**: Improved documentation and functionality
  - Added comprehensive docstring with usage examples
  - Documents superadmin automatic access and wildcard role support
  - Clarifies behavior for `None` (global access) checks
  - Method already existed but now has proper documentation

### Changed
- **Improved Model Documentation**: Enhanced docstrings for `Token` and `UserSetting`
  - Added polymorphic inheritance examples showing how to subclass with custom fields
  - Clarified that `discriminator` field is managed automatically

## [0.8.1] - 2026-01-21

### Added
- **Testing Helpers Module**: Context managers to simplify testing authenticated endpoints
  - `as_user(client, user_id, additional_claims)` - JWT authentication for users
  - `as_admin(client, user_id, additional_claims, roles)` - JWT authentication for admins
  - `clear_registration()` - Reset user context registration
  - Properly sets `HTTP_AUTHORIZATION` header in Flask test client
- **UserProtocol Admin Attributes**: Extended protocol with admin properties
  - `is_admin: bool` - Check if user has admin privileges
  - `is_superadmin: bool` - Check if user has superadmin privileges
  - Ensures type safety for admin checks across custom user implementations

### Fixed
- **Single Table Inheritance (STI) Support**: Fixed automatic `extend_existing=True` injection
  - Removed overly strict check for `has_custom_mapper_args` in `User.__init_subclass__()`
  - Subclasses can now define `__mapper_args__` (e.g., for `polymorphic_identity`)
  - Resolves "Table 'user' is already defined" errors when using STI with custom mapper args
- Removed backward compatibility code: post-super() injection in `User.__init_subclass__()`

### Documentation
- **Testing Guide**: Comprehensive documentation for testing helpers in `docs/testing.rst`
  - Context manager usage examples
  - Testing with fixtures
  - Testing permissions
  - Common patterns for authenticated endpoint testing
- Updated README.md with Testing section and quick examples
- Updated index.rst to include testing guide in table of contents

## [0.8.0] - 2026-01-21

### Added
- **Testing Utilities Module**: Context managers for authenticating as different user types in tests
  - `as_user()` - run code as a specific user
  - `as_admin()` - run code as an admin user
  - `as_superadmin()` - run code as a superadmin user
  - `as_anonymous()` - run code without authentication
  - Properly uses bypass_perms() to simulate authenticated state
- **Protocol Definitions Module**: Centralized protocol definitions for better type safety
  - `ProtocolResolver` - protocol for resolving registered classes
  - `UserProtocol` - interface for User-like objects (moved from user_context)
  - Improves code organization and discoverability

### Changed
- **BREAKING**: User models module reorganized from flat file to package structure
  - `flask_more_smorest.perms.user_models` → `flask_more_smorest.perms.models`
  - New submodules: `role.py`, `setting.py`, `token.py`, `user.py`
  - All imports remain compatible via package-level __init__.py
- **BREAKING**: `user_blueprints.py` renamed to `user_blueprint.py` for consistency
  - Follows singular naming pattern (like `crud_blueprint.py`, `perms_blueprint.py`)
- **UserBlueprint**: Lazy-loaded `user_bp` singleton moved to `flask_more_smorest.perms` module
  - Access via `from flask_more_smorest.perms import user_bp`
  - Provides default pre-configured UserBlueprint instance
- **Documentation cleanup**: Consolidated and reorganized documentation structure
  - Migrated docs from Markdown to ReStructuredText for Sphinx consistency
  - Fixed incorrect API references (e.g., `register_get_current_user` → `register_user_class`)
  - Removed references to non-existent `HasDomainMixin`
  - Fixed cross-references and broken links
  - Updated generated documentation in `docs/_build/`
- **Code quality**: Added type hints to model imports (e.g., `AdminRole` in models/user.py)

### Fixed
- File naming inconsistency: `user_blueprints.py` → `user_blueprint.py` for consistency
- Documentation references to deprecated function names
- Broken imports and cross-references in documentation
- Empty `.ralph/` directory and stale `AGENT_DOCS/` references
- Test naming: `test_multiple_user_blueprints` → `test_multiple_user_blueprint_instances`

### Tests
- Added 18 unit tests for testing utilities (context managers)
- All 270 tests pass with new module structure

### Internal
- Added `.ralph/` to `.gitignore` to exclude Ralph loop state files
- Cleaned up `AGENT_DOCS/` directory for release
- Updated git ignore patterns for development artifacts

## [0.7.1] - 2026-01-13

### Added
- **Superadmin User Context Support**: Complete superadmin support in the user context system
  - `is_current_user_superadmin()` function for checking superadmin status
  - `register_is_current_user_superadmin()` for custom superadmin check registration
  - `BasePermsModel.is_current_user_superadmin()` class method
  - Flask config option: `FMS_IS_CURRENT_USER_SUPERADMIN`
  - Updated `UserProtocol` to include `is_superadmin` property
  - Follows same patterns as existing admin support

### Tests
- Added 10 unit tests for superadmin user context functions
- Added 4 integration tests for superadmin role permissions
- Verifies security boundary: only superadmins can create/modify admin roles

## [0.7.0] - 2026-01-12

### Added
- **Configurable User Context System**: Pluggable authentication system allowing applications to use custom User models
  - Three-tier resolution: Flask config > global registration > built-in fallback
  - `register_user_class()`, `get_current_user()`, `get_current_user_id()`, `is_current_user_admin()` functions
  - `UserProtocol` for type-safe custom User models
  - Flask config options: `FMS_GET_CURRENT_USER`, `FMS_GET_CURRENT_USER_ID`, `FMS_IS_CURRENT_USER_ADMIN`
  - Comprehensive documentation with integration examples (Flask-Login, JWT, OAuth, multi-tenant)
  - Solves SQLAlchemy table name conflicts when applications have existing User models
- **User Context in Error Responses**: Restored user context collection in debug mode error responses
  - Uses configurable user context system (no model conflicts)
  - Shows user ID and roles in debug/testing mode only
  - Works with both built-in and custom User models
  - Gracefully handles missing roles attribute

### Changed
- Permission system now uses configurable user context throughout
- Updated `is_current_user_admin()` to use new user context system
- Error debug context now includes user information via abstracted user context

### Documentation
- New comprehensive guide: Custom User Context (docs/custom-user-context.rst)
- Updated permissions.rst with custom user context cross-reference
- Added concise example in README
- Multiple real-world integration examples

### Tests
- Added 26 unit tests for user context system (253 tests total)
- Tests cover registration, resolution order, Flask config, and edge cases
- Added tests for user context in error responses

## [0.6.0] - 2026-01-11

### Added
- **Health Check Endpoint**: Built-in `/health` endpoint for load balancers and monitoring systems
  - Returns application status, database connectivity, version, and timestamp
  - Configurable via `HEALTH_ENDPOINT_PATH` and `HEALTH_ENDPOINT_ENABLED`
  - Automatically marked as public (no authentication required)
- **SQLAlchemy Performance Monitoring**: Track and log slow database queries
  - Configurable slow query threshold (default: 1.0 seconds)
  - Per-request query statistics via `get_request_query_stats()`
  - Optional logging of all queries at DEBUG level
  - Minimal overhead when disabled
- **Targeted Logging**: Purposeful logging for debugging
  - Permission denial logging with user and resource context
  - Health check failure logging
  - Minimal, production-ready logging approach

### Changed
- **BREAKING**: Error responses now use RFC 7807 Problem Details format
  - Content-Type changed to `application/problem+json`
  - Response structure: `{type, title, status, detail, instance}` (was `{error: {status_code, title, error_code}}`)
  - Debug information (traceback, context) only included in debug/testing mode
  - Configurable error type URI base via `ERROR_TYPE_BASE_URL`
- **Security**: Debug information now environment-aware
  - Tracebacks only included when `app.debug` or `app.testing` is True
  - `UnauthorizedError` never includes traceback
- **Security**: JWT secret key validation in production
  - `init_jwt()` raises `RuntimeError` if `JWT_SECRET_KEY` not set in production
  - Production detected when both `app.debug` and `app.testing` are False

### Fixed
- Filter field validation prevents invalid attribute access
- Improved lazy import error handling with better logging
- Version consistency between package and pyproject.toml

### Internal
- Consolidated duplicate schema and model resolution code (~50 lines removed)
- Unified `resolve_schema()` function for all schema resolution contexts

## [0.5.1] - 2026-01-05

### Changed
- Simplified User extension documentation - removed technical implementation details
- Test suite refactored: extracted schema tests to dedicated file, consolidated small test files
- Condensed CHANGELOG format for better readability

## [0.5.0] - 2026-01-05

### Added
- Case-insensitive email handling (automatic lowercase normalization)
- Automatic table extension for User subclasses (no explicit `__table_args__` needed)

### Fixed
- User model inheritance with function-scoped test fixtures
- SQLAlchemy duplicate class warnings in tests

## [0.4.0] - 2026-01-04

### Added
- Automatic public POST endpoint when `PUBLIC_REGISTRATION = True`

## [0.3.2] - 2026-01-03

### Added
- Comprehensive User inheritance and migration table tests

## [0.3.1] - 2026-01-03

### Changed
- Enhanced UserBlueprint documentation

## [0.3.0] - 2026-01-02

### Added
- **UserBlueprint**: Instant user authentication with login and profile endpoints
- PUBLIC_REGISTRATION support for unauthenticated user creation

## [0.2.3] - 2026-01-02

### Added
- Automatic ReadTheDocs updates via GitHub Actions
- `HasUserMixin.__user_backref_name__` for customizing User relationship backrefs
- PDF and EPUB documentation formats

### Changed
- **UserOwnershipMixin**: Unified permission mixins with `__delegate_to_user__` flag
- Removed unnecessary `__tablename__` declarations (auto-generated names used)

### Fixed
- Domain model foreign key reference

## [0.2.2] - 2026-01-01

### Added
- GitHub workflows for automated PyPI publishing
- Comprehensive CRUD methods logic test suite

### Changed
- Dict mode for `methods` parameter explicitly enables all CRUD methods by default
- Simplified README documentation

### Fixed
- Empty methods list no longer registers empty routes

## [0.2.1] - 2024-12-21

### Changed
- Renamed package from `flask-smorest-crud` to `flask-more-smorest`
- Moved to proper package structure under `flask_more_smorest/`

### Added
- Initial PyPI package structure
- GitHub Actions CI/CD pipeline
- Pre-commit hooks
- Type hints throughout

## [0.1.0] - 2024-11-22

### Added
- Initial public release
- `CRUDBlueprint` for automatic CRUD operations
- `EnhancedBlueprint` with public/admin decorators
- Query filtering with range and comparison operators
- Automatic operationId generation
- SQLAlchemy 2.0+ support

## [0.0.1] - 2024-11-22

### Added
- Initial development version
