# PyPI Publishing Checklist

Quick reference for publishing `flask-more-smorest` to PyPI.

## One-Time Setup

### Option A: Trusted Publishing (Recommended)

**On PyPI** (https://pypi.org):
- [ ] Log in with qualisero credentials
- [ ] Go to Publishing settings
- [ ] Add publisher with:
  - PyPI Project: `flask-more-smorest`
  - Owner: `qualisero`
  - Repository: `flask-more-smorest`
  - Workflow: `ci-cd.yml`
  - Environment: `pypi`

**On GitHub**:
- [ ] Go to Settings → Environments
- [ ] Create environment: `pypi`
- [ ] (Optional) Add protection rules

### Option B: API Token

**On PyPI**:
- [ ] Generate API token for `flask-more-smorest`
- [ ] Copy token

**On GitHub**:
- [ ] Add secret: `PYPI_API_TOKEN`
- [ ] Paste token value

## Publishing a New Release

- [ ] Ensure all tests pass locally: `poetry run pytest`
- [ ] Ensure linting passes: `poetry run black . && poetry run isort . && poetry run flake8`
- [ ] Update version: `poetry version <patch|minor|major>`
- [ ] Update CHANGELOG.md
- [ ] Commit changes: `git commit -am "Bump version to X.Y.Z"`
- [ ] Push to main: `git push`
- [ ] Create GitHub release with tag (e.g., `v0.2.1`)
- [ ] Verify workflow runs successfully
- [ ] Check package on PyPI: https://pypi.org/project/flask-more-smorest/

## Verification

After publishing:
- [ ] Package appears on PyPI
- [ ] Install in fresh environment: `pip install flask-more-smorest`
- [ ] Test basic import: `python -c "import flask_more_smorest"`
- [ ] Check package metadata on PyPI page

## Troubleshooting

If publish fails:
1. Check workflow logs in GitHub Actions
2. Verify PyPI credentials/configuration
3. Ensure version was incremented
4. See `.github/PYPI_PUBLISHING.md` for detailed help
