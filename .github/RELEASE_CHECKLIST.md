# Release Checklist

Quick checklist for releasing a new version of flask-more-smorest.

## Pre-Release

- [ ] All tests passing locally: `pytest tests/`
- [ ] Code linted: `black . && isort . && flake8`
- [ ] Update CHANGELOG.md with changes for this release

## Version Bump

```bash
# Bump version (patch, minor, or major)
poetry version patch  # or minor, major

# Get the new version
NEW_VERSION=$(poetry version -s)
echo "New version: $NEW_VERSION"
```

## Update Badge Version

Update the version query parameter in README.md badges:

```bash
# Update badges with new version
sed -i '' "s/\?v=[0-9]\+\.[0-9]\+\.[0-9]\+/?v=$NEW_VERSION/g" README.md

# Or manually edit README.md and update:
# [![PyPI version](https://badge.fury.io/py/flask-more-smorest.svg?v=X.Y.Z)]
# [![Python Support](https://img.shields.io/pypi/pyversions/flask-more-smorest.svg?v=X.Y.Z)]
```

## Commit and Release

```bash
# Commit changes
git add pyproject.toml CHANGELOG.md README.md
git commit -m "Bump version to $NEW_VERSION"

# Push to main
git push origin main

# Create GitHub release (triggers CI/CD and PyPI publish)
gh release create v$NEW_VERSION \
  --title "Release v$NEW_VERSION" \
  --notes-file RELEASE_NOTES.md  # or use --generate-notes

# Or with inline notes:
gh release create v$NEW_VERSION \
  --title "Release v$NEW_VERSION" \
  --notes "## What's Changed
- Feature 1
- Feature 2
- Bug fix 1

**Full Changelog**: https://github.com/qualisero/flask-more-smorest/compare/v0.2.1...v$NEW_VERSION"
```

## Verify Release

- [ ] Check GitHub Actions workflow: `gh run list --limit 1`
- [ ] Wait for workflow completion: `gh run watch <run-id>`
- [ ] Verify on PyPI: https://pypi.org/project/flask-more-smorest/
- [ ] Test installation: `pip install flask-more-smorest==$NEW_VERSION`

## Post-Release

- [ ] Update any documentation that references version numbers
- [ ] Announce release (if applicable)
- [ ] Close related issues/PRs

## Automated Script

For convenience, you can use this one-liner:

```bash
# Example: Bump patch version and update badges
NEW_VERSION=$(poetry version patch | awk '{print $6}') && \
sed -i '' "s/?v=[0-9]\+\.[0-9]\+\.[0-9]\+/?v=$NEW_VERSION/g" README.md && \
echo "Updated to version $NEW_VERSION - remember to update CHANGELOG.md!"
```

## Notes

- Badge version query param (`?v=X.Y.Z`) forces CDN cache refresh
- GitHub Actions automatically publishes to PyPI on release creation
- Uses PyPI Trusted Publishing (no API tokens needed)
- See `.github/PYPI_PUBLISHING.md` for detailed publishing setup
