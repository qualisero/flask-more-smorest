#!/bin/bash
# Bump version and create a GitHub release
# Usage: ./scripts/bump_version.sh [patch|minor|major]

set -e

BUMP_TYPE=${1:-patch}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Running pre-release checks..."

# Check if on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "${YELLOW}⚠️  Warning: Not on main branch (currently on: $CURRENT_BRANCH)${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ Error: You have uncommitted changes${NC}"
    echo "Please commit or stash your changes before bumping version"
    exit 1
fi

# Run tests
echo "🧪 Running tests..."
if ! poetry run pytest -q; then
    echo -e "${RED}❌ Tests failed! Fix tests before releasing.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ All tests passed${NC}"

# Run type checks
echo "🔍 Running pyright type checks..."
if ! poetry run pyright; then
    echo -e "${RED}❌ Type checks failed! Fix type errors before releasing.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Type checks passed${NC}"

echo ""
echo "🔄 Bumping $BUMP_TYPE version..."
poetry version "$BUMP_TYPE"
NEW_VERSION=$(poetry version -s)

if [ -z "$NEW_VERSION" ]; then
    echo -e "${RED}❌ Failed to bump version${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Version bumped to: $NEW_VERSION${NC}"

# Determine sed -i flag (BSD sed requires an explicit empty suffix; GNU sed does not)
if [[ "$OSTYPE" == "darwin"* ]]; then
    SED_INPLACE=(-i '')
else
    SED_INPLACE=(-i)
fi

echo "🔄 Updating __version__ in __init__.py..."
INIT_FILE="flask_more_smorest/__init__.py"
sed "${SED_INPLACE[@]}" "s/__version__ = \"[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\"/__version__ = \"$NEW_VERSION\"/g" "$INIT_FILE"
if ! grep -q "__version__ = \"$NEW_VERSION\"" "$INIT_FILE"; then
    echo -e "${RED}❌ Failed to update __version__ in $INIT_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ __init__.py updated${NC}"

echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "   1. Update CHANGELOG.md with release notes for v$NEW_VERSION"
echo "      - Add ## [${NEW_VERSION}] - $(date +%Y-%m-%d)"
echo "      - Document Added, Changed, Fixed sections"
echo ""
echo "   2. Review changes:"
echo "      git diff"
echo ""
echo "   3. Commit and push:"
echo "      git add pyproject.toml flask_more_smorest/__init__.py CHANGELOG.md"
echo "      git commit -m 'chore: bump version to $NEW_VERSION'"
echo "      git push origin main"
echo ""
echo "   4. Create and push tag:"
echo "      git tag -a v$NEW_VERSION -m 'Release v$NEW_VERSION'"
echo "      git push origin v$NEW_VERSION"
echo ""
echo "   5. Create GitHub release (triggers PyPI publish + docs update):"
echo "      gh release create v$NEW_VERSION --title 'v$NEW_VERSION - Title Here' --notes 'Release notes here'"
echo ""
echo -e "${GREEN}✨ After GitHub release is created, CI/CD will automatically:${NC}"
echo "   - Run tests (Python 3.11 to 3.14)"
echo "   - Run linting, typing and security checks"
echo "   - Build package"
echo "   - Publish to PyPI (via Trusted Publishing)"
echo "   - Trigger ReadTheDocs build"
echo ""
echo -e "${YELLOW}💡 Tip: You can check CI/CD progress with:${NC}"
echo "   gh run watch"
