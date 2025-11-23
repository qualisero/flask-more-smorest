# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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