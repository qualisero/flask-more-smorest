#!/bin/bash
# Bump version and create a GitHub release
# Usage: ./scripts/bump_version.sh [patch|minor|major]

set -e

BUMP_TYPE=${1:-patch}

echo "🔄 Bumping $BUMP_TYPE version..."
NEW_VERSION=$(poetry version $BUMP_TYPE | awk '{print $6}')

if [ -z "$NEW_VERSION" ]; then
    echo "❌ Failed to bump version"
    exit 1
fi

echo "✅ Version bumped to: $NEW_VERSION"

echo "🔄 Updating badge versions in README.md..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/?v=[0-9]\+\.[0-9]\+\.[0-9]\+/?v=$NEW_VERSION/g" README.md
else
    # Linux
    sed -i "s/?v=[0-9]\+\.[0-9]\+\.[0-9]\+/?v=$NEW_VERSION/g" README.md
fi

echo "✅ Badges updated"

echo ""
echo "📝 Next steps:"
echo "   1. Update CHANGELOG.md with release notes for v$NEW_VERSION"
echo "   2. Review changes: git diff"
echo "   3. Commit and tag:"
echo "      git add pyproject.toml CHANGELOG.md README.md"
echo "      git commit -m 'Bump version to $NEW_VERSION'"
echo "      git tag v$NEW_VERSION"
echo "      git push origin main --tags"
echo "   4. Create GitHub release (triggers PyPI publish + docs update):"
echo "      gh release create v$NEW_VERSION --title 'v$NEW_VERSION' --notes-file RELEASE_NOTES.md"
echo ""
echo "✨ After release, CI/CD will automatically:"
echo "   - Run tests and linting"
echo "   - Publish to PyPI"
echo "   - Update ReadTheDocs (if token configured)"
