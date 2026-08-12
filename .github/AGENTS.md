# Flask-More-Smorest Project Agents

Project-specific agent instructions for flask-more-smorest development and releases.

## Release Process

### Standard Release (from main branch)

When asked to create a release:

1. **Ensure all changes are committed and tests pass:**
   ```bash
   poetry run pytest
   poetry run mypy flask_more_smorest
   ```

2. **Run bump version script:**
   ```bash
   ./scripts/bump_version.sh [patch|minor|major]
   ```
   
   This script will:
   - Check for uncommitted changes
   - Run tests and mypy checks
   - Bump version in `pyproject.toml`
   - Update `__version__` in `flask_more_smorest/__init__.py`

3. **Update CHANGELOG.md** with release notes following [Keep a Changelog](https://keepachangelog.com/) format:
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD
   
   ### Added
   - New features
   
   ### Changed
   - Changes in existing functionality
   
   ### Fixed
   - Bug fixes
   ```

4. **Commit and push:**
   ```bash
   git add pyproject.toml flask_more_smorest/__init__.py CHANGELOG.md
   git commit -m "chore: bump version to X.Y.Z"
   git push origin main
   ```

5. **Create and push tag:**
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. **Create GitHub release:**
   ```bash
   gh release create vX.Y.Z \
     --title "vX.Y.Z - Title" \
     --notes "## Release Notes
   
   [Detailed notes here]"
   ```

7. **Automation:** GitHub Actions will automatically:
   - Run tests (Python 3.11 to 3.14)
   - Run linting and security checks (ruff, including the S ruleset)
   - Build package
   - Publish to PyPI (via Trusted Publishing/OIDC)
   - Trigger ReadTheDocs build

8. **Verify release:**
   ```bash
   # Watch CI/CD progress
   gh run watch
   
   # Verify PyPI publication
   curl -s https://pypi.org/pypi/flask-more-smorest/json | jq -r '.info.version'
   ```

### Feature Branch Release Workflow

When releasing from a feature branch:

1. **Develop on feature branch:**
   ```bash
   git checkout -b feature/your-feature
   # Make changes
   git commit -m "feat: your feature"
   ```

2. **Run pre-merge checks:**
   ```bash
   poetry run pytest -xvs
   poetry run mypy flask_more_smorest
   ```

3. **Push feature branch:**
   ```bash
   git push origin feature/your-feature
   ```

4. **Merge to main:**
   ```bash
   git checkout main
   git merge feature/your-feature --no-ff
   git push origin main
   ```

5. **Follow standard release process** (steps 2-8 above)

## Pre-Release Checklist

Before running `bump_version.sh`:

- [ ] All tests pass: `poetry run pytest`
- [ ] Type checks pass: `poetry run mypy flask_more_smorest`
- [ ] Linting passes: `poetry run ruff check flask_more_smorest`
- [ ] All changes committed
- [ ] On main branch (or have plan for feature branch merge)
- [ ] CHANGELOG.md is ready to update

## Files Modified During Release

The release process modifies these files:

1. **`pyproject.toml`** - Version number (via Poetry)
2. **`flask_more_smorest/__init__.py`** - `__version__` attribute
3. **`CHANGELOG.md`** - Release notes

All files must be committed together in the version bump commit.

## Code Style

- Use auto-generated `__tablename__` (snake_case from class name)
- No explicit `__tablename__` unless custom name required
- Follow existing patterns in codebase
- All tests must pass before release
- Type hints required (mypy checks enforced)

## Documentation

- Update docstrings when changing APIs
- Add examples for new features
- Keep CHANGELOG.md current using [Keep a Changelog](https://keepachangelog.com/) format
- ReadTheDocs auto-updates on release

## Testing

- Run full test suite: `poetry run pytest`
- Ensure 100% pass rate before release
- Add tests for new features
- Zero warnings policy
- Type check: `poetry run mypy flask_more_smorest`

## CI/CD Pipeline

### Triggered On
- **Push to main**: Runs tests and linting
- **Release creation**: Full pipeline + publish to PyPI + docs update
- **Pull requests**: Tests and checks only

### Jobs
1. **test** - Python 3.11 to 3.14 test matrix
2. **lint** - Ruff formatting, linting (including the S security ruleset) and mypy
3. **build** - Build Python package
4. **publish** - Publish to PyPI (release only, via Trusted Publishing)
5. **trigger-docs** - Trigger ReadTheDocs build (release only)

### Trusted Publishing
- PyPI publication uses GitHub OIDC (no tokens needed)
- Configured on PyPI for trusted publishing from GitHub Actions
- Automatic and secure

## Troubleshooting

### Version Mismatch Errors
If `__init__.py` version doesn't match `pyproject.toml`:
```bash
# Manually sync versions
VERSION=$(poetry version -s)
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" flask_more_smorest/__init__.py
```

### Tests Fail Before Release
```bash
# Run tests with verbose output
poetry run pytest -xvs

# Check for mypy issues
poetry run mypy flask_more_smorest
```

### PyPI Publication Fails
- Check GitHub Actions logs: `gh run view`
- Verify Trusted Publishing is configured on PyPI
- Ensure release was created (not just tag)

### ReadTheDocs Not Updating
- Verify webhook is configured on GitHub
- Check ReadTheDocs build logs
- Trigger manual build on ReadTheDocs dashboard

## Quick Commands Reference

```bash
# Start a release
./scripts/bump_version.sh minor

# Check status
git status
git diff

# Complete release
git add -A
git commit -m "chore: bump version to X.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes "Release notes"

# Monitor
gh run watch
```
