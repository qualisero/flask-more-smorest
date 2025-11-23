# Contributing to Flask-More-Smorest

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Poetry for dependency management
- Git

### Setup Instructions

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/yourusername/flask-more-smorest.git
   cd flask-more-smorest
   ```

2. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies**:
   ```bash
   poetry install
   ```

4. **Install pre-commit hooks**:
   ```bash
   poetry run pre-commit install
   ```

5. **Run tests to verify setup**:
   ```bash
   poetry run pytest
   ```

## Development Workflow

### Making Changes

1. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines below.

3. **Add tests** for any new functionality:
   ```bash
   # Add tests in tests/
   poetry run pytest tests/test_your_feature.py
   ```

4. **Run the full test suite**:
   ```bash
   poetry run pytest
   poetry run pytest --cov=flask_more_smorest
   ```

5. **Run linting and formatting**:
   ```bash
   poetry run black flast-more-smorest/ tests/
   poetry run flake8 flast-more-smorest/ tests/
   poetry run mypy flast-more-smorest/
   ```

6. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

### Code Style Guidelines

- **Follow PEP 8** for Python code style
- **Use Black** for code formatting (line length: 120)
- **Add type hints** for all new functions and classes
- **Write docstrings** using Google style for all public APIs
- **Use meaningful variable and function names**

#### Example Code Style

```python
from typing import Optional, List, Dict, Any

def process_user_data(
    user_data: Dict[str, Any], 
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """Process user data and return filtered results.
    
    Args:
        user_data: Dictionary containing user information
        include_inactive: Whether to include inactive users
        
    Returns:
        List of processed user dictionaries
        
    Raises:
        ValueError: If user_data is malformed
    """
    # Implementation here
    pass
```

### Testing Guidelines

- **Write unit tests** for all new functionality
- **Use pytest fixtures** for common test setup
- **Aim for >90% test coverage**
- **Test edge cases and error conditions**
- **Use descriptive test names**

#### Test Example

```python
import pytest
from flask_more_smorest import CRUDBlueprint

def test_crud_blueprint_creation():
    """Test that CRUDBlueprint can be created with minimal parameters."""
    blueprint = CRUDBlueprint('users', __name__)
    assert blueprint.name == 'users'
    assert blueprint.url_prefix == '/users/'

def test_crud_blueprint_with_custom_model():
    """Test CRUDBlueprint with custom model and schema names."""
    blueprint = CRUDBlueprint(
        'products', __name__,
        model='Product',
        schema='ProductSchema'
    )
    # Assert expected behavior
```

### Commit Message Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add support for custom filtering operators
fix: resolve issue with datetime range filtering
docs: update README with new examples
test: add unit tests for query filtering
```

## Pull Request Process

1. **Update documentation** if needed (README, docstrings, etc.)
2. **Update CHANGELOG.md** with your changes
3. **Ensure all tests pass** and coverage remains high
4. **Create a pull request** with a clear description
5. **Respond to code review feedback** promptly

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] All existing tests pass

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review of code completed
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated
```

## Reporting Issues

### Bug Reports

Include the following information:
- **Python version**
- **Package versions** (run `poetry show`)
- **Minimal code example** that reproduces the issue
- **Expected vs actual behavior**
- **Error messages or stack traces**

### Feature Requests

- **Clear description** of the proposed feature
- **Use case or motivation** for the feature
- **Proposed API or interface** if applicable
- **Willingness to implement** the feature yourself

## Code Review Process

- All submissions require review before merging
- Maintainers will review PRs within a reasonable timeframe
- Address feedback constructively and promptly
- Be respectful and professional in all interactions

## Questions?

If you have questions about contributing, feel free to:
- Open an issue for discussion
- Reach out to the maintainers
- Check existing documentation and issues first

## Recognition

Contributors will be recognized in the project documentation and release notes. Thank you for helping make this project better!