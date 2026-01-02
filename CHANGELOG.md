# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-01-01

### Changed
- **BREAKING CLARIFICATION**: When using dict mode for `methods` parameter in `CRUDBlueprint`, all CRUD methods are now explicitly enabled by default. Previously this behavior was undocumented.
- Simplified README documentation for `methods` parameter, removed `skip_methods` details from main docs
- Enhanced docstrings in `CRUDBlueprint` with comprehensive examples
- Improved error messages with type information in method normalization

### Added
- Warning when both dict `False` and `skip_methods` are used redundantly for the same method
- Comprehensive test suite for `methods` and `skip_methods` logic (11 new tests)
- Documentation file `docs/crud_methods_cleanup.md` explaining method resolution
- GitHub workflows for automated PyPI publishing with Trusted Publishing support

### Fixed
- Empty methods list no longer attempts to register empty MethodView routes
- GenericCRUD route only registered when it has at least one method

## [0.2.1] - 2024-12-21

### Changed
- Renamed package from `flask-smorest-crud` to `flask-more-smorest`
- Updated all import statements and references
- Updated PyPI package name and repository URLs

### Added
- Initial PyPI package structure
- Comprehensive documentation and examples
- GitHub Actions CI/CD pipeline
- Pre-commit hooks configuration
- Type hints for all modules
- Unit tests with pytest framework

### Changed
- Moved source code to proper package structure under `flask_more_smorest/`
- Updated pyproject.toml with complete package metadata
- Enhanced docstrings following Google style guide

### Fixed
- Import paths updated for new package structure

## [0.1.0] - 2024-11-22

### Added
- Initial public release
- `CRUDBlueprint` class for automatic CRUD operations
- `EnhancedBlueprint` with public/admin endpoint decorators
- Query filtering utilities with range and comparison operators
- Automatic operationId generation for OpenAPI documentation
- Support for SQLAlchemy 2.0+ and Flask-Smorest integration

### Features
- Automatic RESTful API generation from SQLAlchemy models
- Advanced filtering for datetime, numeric, and string fields
- Type hints and modern Python 3.11+ support
- Comprehensive documentation and examples

## [0.0.1] - 2024-11-22

### Added
- Initial development version
- Core CRUD functionality implementation
- Basic blueprint extensions
- Query filtering prototype