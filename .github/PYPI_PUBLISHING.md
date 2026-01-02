# PyPI Publishing Setup

This document describes how to set up automated publishing to PyPI for the `flask-more-smorest` package under the `qualisero` organization.

## Package Details

- **Package Name**: `flask-more-smorest`
- **Organization**: qualisero
- **Repository**: https://github.com/qualisero/flask-more-smorest
- **PyPI URL**: https://pypi.org/project/flask-more-smorest/

## Publishing Methods

The workflow supports **two methods** for publishing to PyPI:

### Method 1: Trusted Publishing (OIDC) - **RECOMMENDED**

Trusted Publishing is the modern, secure way to publish to PyPI without using API tokens. It uses OpenID Connect (OIDC) to authenticate GitHub Actions directly with PyPI.

#### Setup Steps:

1. **On PyPI** (https://pypi.org):
   - Log in to your PyPI account (must have owner/maintainer access for the package)
   - Go to your account settings → Publishing
   - Click "Add a new publisher"
   - Fill in:
     - **PyPI Project Name**: `flask-more-smorest`
     - **Owner**: `qualisero`
     - **Repository name**: `flask-more-smorest`
     - **Workflow name**: `ci-cd.yml`
     - **Environment name**: `pypi`
   - Save the configuration

2. **On GitHub**:
   - Go to repository Settings → Environments
   - Create an environment named `pypi`
   - (Optional) Add protection rules:
     - Required reviewers
     - Wait timer
     - Deployment branches (e.g., only `main`)

That's it! No secrets needed.

#### Benefits:
- ✅ No API tokens to manage or rotate
- ✅ More secure (short-lived credentials)
- ✅ Recommended by PyPI
- ✅ Easier to audit

### Method 2: API Token - **FALLBACK**

If Trusted Publishing is not set up, you can use a traditional API token.

#### Setup Steps:

1. **On PyPI**:
   - Log in to your PyPI account
   - Go to Account settings → API tokens
   - Click "Add API token"
   - Set scope to "Project: flask-more-smorest" (or use account-wide token)
   - Copy the token (starts with `pypi-`)

2. **On GitHub**:
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Paste the token from PyPI
   - Save

3. **Update the workflow** (if needed):
   - The current workflow prioritizes Trusted Publishing
   - To force API token usage, modify the publish step to use Poetry:
   ```yaml
   - name: Publish to PyPI
     env:
       POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_API_TOKEN }}
     run: |
       poetry publish --no-interaction
   ```

## Publishing Process

### Automatic Publishing on Release

1. Make sure all changes are committed and tests pass
2. Update version in `pyproject.toml`:
   ```bash
   poetry version patch  # or minor, major, prepatch, etc.
   git add pyproject.toml
   git commit -m "Bump version to X.Y.Z"
   git push
   ```

3. Create a GitHub release:
   - Go to repository → Releases → "Draft a new release"
   - Create a new tag (e.g., `v0.2.1`)
   - Set release title (e.g., "Release v0.2.1")
   - Add release notes
   - Click "Publish release"

4. The workflow will automatically:
   - Run all tests
   - Run linting and security checks
   - Build the package
   - Publish to PyPI

### Manual Publishing (Workflow Dispatch)

For testing or emergency releases:

1. Go to Actions → CI/CD Pipeline
2. Click "Run workflow"
3. Select branch
4. Check "Publish to PyPI"
5. Click "Run workflow"

## Workflow Details

The CI/CD pipeline includes these jobs:

1. **test**: Runs tests on Python 3.11 and 3.12
2. **lint**: Checks code style with black, isort, flake8, mypy
3. **security**: Runs bandit security checks
4. **build**: Builds the package (wheel and sdist)
5. **publish**: Publishes to PyPI

The workflow triggers on:
- Push to `main` or `develop` branches (test only)
- Pull requests to `main` or `develop` (test only)
- Published releases (full pipeline including publish)
- Manual workflow dispatch (optional publish)

## Versioning

This project uses semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backwards-compatible)
- **PATCH**: Bug fixes (backwards-compatible)

Use Poetry to update versions:
```bash
poetry version patch   # 0.2.0 → 0.2.1
poetry version minor   # 0.2.0 → 0.3.0
poetry version major   # 0.2.0 → 1.0.0
poetry version prepatch # 0.2.0 → 0.2.1-alpha.0
```

## Troubleshooting

### Error: "The user 'xxx' isn't allowed to upload to project 'flask-more-smorest'"

**Solution**: The PyPI account used doesn't have permission. Add the user as a maintainer on PyPI.

### Error: "Trusted publishing exchange failure"

**Solution**: 
1. Verify the Trusted Publisher is configured correctly on PyPI
2. Check that environment name matches (`pypi`)
3. Ensure workflow name is correct (`ci-cd.yml`)
4. Verify repository owner and name are correct

### Error: "Invalid or non-existent authentication information"

**Solution**: If using API tokens, verify:
1. Token exists in GitHub Secrets as `PYPI_API_TOKEN`
2. Token hasn't expired
3. Token has correct scope

### Package won't publish - "File already exists"

**Solution**: 
1. You cannot re-upload the same version to PyPI
2. Increment the version in `pyproject.toml`
3. Create a new release

### Tests fail in workflow but pass locally

**Solution**:
1. Check Python version compatibility
2. Verify all dependencies are in `pyproject.toml`
3. Look for environment-specific issues
4. Check the workflow logs for details

## Security Considerations

- ✅ Use Trusted Publishing when possible
- ✅ Limit API token scope to single project
- ✅ Use GitHub environment protection for releases
- ✅ Require review before deployment
- ✅ Keep dependencies up to date
- ✅ Run security scans (bandit) before publishing

## Additional Resources

- [PyPI Trusted Publishers Guide](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions Publishing](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [Poetry Publishing Docs](https://python-poetry.org/docs/libraries/#publishing-to-pypi)
