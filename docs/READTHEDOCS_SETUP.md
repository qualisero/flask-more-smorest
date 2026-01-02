# ReadTheDocs Automatic Updates on Release

This document explains how automatic documentation updates are configured for flask-more-smorest.

## Overview

When a new release is published on GitHub, the documentation on ReadTheDocs is automatically updated through the following workflow:

1. Developer creates a new release on GitHub
2. GitHub Actions CI/CD pipeline runs:
   - Runs tests, linting, and security checks
   - Builds the package
   - Publishes to PyPI
   - **Triggers ReadTheDocs build via API**
3. ReadTheDocs rebuilds documentation with the new version
4. Updated docs are live at https://flask-more-smorest.readthedocs.io

## Configuration Files

### 1. `.readthedocs.yaml`

This file configures ReadTheDocs to:
- Use Python 3.12
- Build Sphinx documentation from `docs/conf.py`
- Install the package with dev dependencies
- Generate PDF and EPUB formats

Key configuration:
```yaml
version: 2
build:
  os: ubuntu-22.04
  tools:
    python: "3.12"
sphinx:
  configuration: docs/conf.py
python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - dev
formats:
  - pdf
  - epub
```

### 2. `.github/workflows/ci-cd.yml`

The CI/CD pipeline includes a `trigger-docs` job that:
- Runs after successful PyPI publication
- Only triggers on release events
- Calls the ReadTheDocs API to rebuild documentation

```yaml
trigger-docs:
  runs-on: ubuntu-latest
  needs: [publish]
  if: github.event_name == 'release'
  steps:
    - name: Trigger ReadTheDocs build
      run: |
        curl -X POST \
          -H "Authorization: Token ${{ secrets.READTHEDOCS_TOKEN }}" \
          https://readthedocs.org/api/v3/projects/flask-more-smorest/versions/latest/builds/
```

## Required Setup

### Step 1: ReadTheDocs Project Setup

1. Go to https://readthedocs.org/dashboard/
2. Import the project from GitHub
3. Project settings:
   - **Name**: flask-more-smorest
   - **Repository URL**: https://github.com/qualisero/flask-more-smorest
   - **Default branch**: main
   - **Default version**: latest

### Step 2: Enable Version Builds

In ReadTheDocs project settings:

1. Go to **Admin** → **Automation Rules**
2. Add rule: "Activate version on tag push"
   - **Match**: `v*` (matches v0.2.2, v1.0.0, etc.)
   - **Version type**: Tag
   - **Action**: Activate version and build

### Step 3: Generate ReadTheDocs API Token

1. Go to https://readthedocs.org/accounts/tokens/
2. Click "Create Token"
3. Name: `GitHub Actions CI/CD`
4. Copy the token (you won't see it again!)

### Step 4: Add Token to GitHub Secrets

1. Go to https://github.com/qualisero/flask-more-smorest/settings/secrets/actions
2. Click "New repository secret"
3. Name: `READTHEDOCS_TOKEN`
4. Value: (paste the token from Step 3)
5. Click "Add secret"

### Step 5: Configure Webhooks (Optional but Recommended)

ReadTheDocs should automatically set up webhooks, but you can verify:

1. Go to https://github.com/qualisero/flask-more-smorest/settings/hooks
2. Check for a webhook pointing to `readthedocs.org`
3. If missing, add it:
   - **Payload URL**: `https://readthedocs.org/api/v2/webhook/flask-more-smorest/`
   - **Content type**: `application/json`
   - **Events**: 
     - Branch or tag creation
     - Branch or tag deletion
     - Pushes
     - Releases

## Testing the Setup

### Manual Trigger

Test the ReadTheDocs build without creating a release:

```bash
curl -X POST \
  -H "Authorization: Token YOUR_READTHEDOCS_TOKEN" \
  https://readthedocs.org/api/v3/projects/flask-more-smorest/versions/latest/builds/
```

### Release Workflow

1. Update version in `pyproject.toml`
2. Commit and push changes
3. Create a new release on GitHub:
   ```bash
   git tag v0.2.3
   git push origin v0.2.3
   ```
4. Go to GitHub → Releases → "Draft a new release"
5. Select the tag, add release notes, publish
6. Watch the Actions tab for the workflow
7. Verify docs update at https://flask-more-smorest.readthedocs.io

## Troubleshooting

### Docs Not Building

**Check ReadTheDocs Build Logs:**
1. Go to https://readthedocs.org/projects/flask-more-smorest/builds/
2. Click on the failed build
3. Review the build log for errors

**Common Issues:**
- **Missing dependencies**: Update `docs/requirements.txt`
- **Sphinx warnings**: Check `docs/conf.py` configuration
- **Python version mismatch**: Ensure `.readthedocs.yaml` uses correct Python version

### API Trigger Failing

**Check GitHub Actions Logs:**
1. Go to https://github.com/qualisero/flask-more-smorest/actions
2. Click on the failed workflow
3. Expand the "Trigger ReadTheDocs build" step

**Common Issues:**
- **Invalid token**: Regenerate and update `READTHEDOCS_TOKEN` secret
- **Wrong project slug**: Verify project name in the API URL
- **Rate limiting**: Wait a few minutes and try again

### Webhook Not Firing

**Verify Webhook:**
1. Go to GitHub repository → Settings → Webhooks
2. Click on the ReadTheDocs webhook
3. Check "Recent Deliveries" tab
4. Look for successful (200) or failed deliveries

**Re-add Webhook:**
1. Delete existing webhook
2. Go to ReadTheDocs → Admin → Integrations
3. Click "Resync webhook"

## Versioning Strategy

ReadTheDocs provides multiple documentation versions:

### Version Types

**`latest`** (Development Documentation)
- Tracks: `main` branch
- Updates: On every push to main
- Contains: Unreleased features and changes
- URL: `https://flask-more-smorest.readthedocs.io/en/latest/`
- Use case: Developers working on the project

**`stable`** (Production Documentation)
- Tracks: Most recent release tag
- Updates: Only when a new release is created
- Contains: Current production version
- URL: `https://flask-more-smorest.readthedocs.io/en/stable/`
- Use case: End users installing from PyPI

**Tagged Versions** (e.g., `v0.2.3`, `v0.2.4`)
- Tracks: Specific release tags
- Updates: Never (frozen at release time)
- Contains: Documentation for that specific version
- URL: `https://flask-more-smorest.readthedocs.io/en/v0.2.3/`
- Use case: Users on older versions

### Recommended Links

For users in README/documentation:
```markdown
📚 **Documentation**: https://flask-more-smorest.readthedocs.io/en/stable/
```

For developers:
```markdown
🔧 **Dev Docs**: https://flask-more-smorest.readthedocs.io/en/latest/
```

### What GitHub Actions Triggers

When you create a release, the workflow triggers builds for:
1. ✅ `latest` - Rebuilds from main branch
2. ✅ `stable` - Rebuilds from latest release tag
3. ✅ ReadTheDocs automatically builds the new tag version

This ensures all documentation is up-to-date after a release.

## Additional Resources

- [ReadTheDocs Documentation](https://docs.readthedocs.io/)
- [ReadTheDocs API](https://docs.readthedocs.io/en/stable/api/v3.html)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Sphinx Documentation](https://www.sphinx-doc.org/)

## Maintenance

### Updating ReadTheDocs Configuration

To modify documentation build settings:

1. Edit `.readthedocs.yaml`
2. Commit and push changes
3. ReadTheDocs will automatically use the new configuration

### Updating CI/CD Workflow

To modify the release workflow:

1. Edit `.github/workflows/ci-cd.yml`
2. Commit and push changes
3. Test with a draft release

---

**Last Updated**: January 2, 2026  
**Maintainer**: Qualisero Team
