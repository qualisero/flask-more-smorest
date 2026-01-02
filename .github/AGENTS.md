# Flask-More-Smorest Project Agents

Project-specific agent instructions for flask-more-smorest development and releases.

## Release Process

When asked to create a release:

1. **Run bump version script:**
   ```bash
   ./scripts/bump_version.sh [patch|minor|major]
   ```

2. **Update CHANGELOG.md** with release notes following Keep a Changelog format

3. **Commit and tag:**
   ```bash
   git add pyproject.toml CHANGELOG.md README.md
   git commit -m "Bump version to X.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```

4. **Create GitHub release:**
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes-file /tmp/release-notes.md
   ```

5. **Automation:** GitHub Actions will automatically:
   - Run tests (Python 3.11 & 3.12)
   - Run linting and security checks
   - Build package
   - Publish to PyPI (via Trusted Publishing)
   - Trigger ReadTheDocs build (if token configured)

## Code Style

- Use auto-generated `__tablename__` (snake_case from class name)
- No explicit `__tablename__` unless custom name required
- Follow existing patterns in codebase
- All tests must pass before release

## Documentation

- Update docstrings when changing APIs
- Add examples for new features
- Keep CHANGELOG.md current
- ReadTheDocs auto-updates on release

## Testing

- Run full test suite: `poetry run pytest`
- Ensure 100% pass rate
- Add tests for new features
- Zero warnings policy
