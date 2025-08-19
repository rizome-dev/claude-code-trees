#!/bin/bash
# Release script for claude-code-trees
# Usage: ./scripts/release.sh [patch|minor|major]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default to patch version
VERSION_TYPE=${1:-patch}

echo -e "${GREEN}🚀 Preparing release for claude-code-trees${NC}"

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
echo -e "${YELLOW}Current version: $CURRENT_VERSION${NC}"

# Calculate new version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

case $VERSION_TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo -e "${RED}Invalid version type. Use: patch, minor, or major${NC}"
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo -e "${GREEN}New version: $NEW_VERSION${NC}"

# Update version in pyproject.toml
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Update version in __init__.py if it exists
if [ -f "src/claude_code_trees/__init__.py" ]; then
    if grep -q "__version__" src/claude_code_trees/__init__.py; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" src/claude_code_trees/__init__.py
        else
            sed -i "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" src/claude_code_trees/__init__.py
        fi
    else
        echo "__version__ = \"$NEW_VERSION\"" >> src/claude_code_trees/__init__.py
    fi
fi

# Prompt for changelog entry
echo -e "${YELLOW}Enter changelog entry for v$NEW_VERSION (press Ctrl+D when done):${NC}"
CHANGELOG_ENTRY=$(cat)

# Update CHANGELOG.md
if [ -f "CHANGELOG.md" ]; then
    # Create temporary file with new entry
    cat > /tmp/changelog_new.md << EOF
# Changelog

All notable changes to Claude Code Trees will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [$NEW_VERSION] - $(date +%Y-%m-%d)

$CHANGELOG_ENTRY

EOF
    
    # Append rest of changelog (skipping header)
    tail -n +7 CHANGELOG.md >> /tmp/changelog_new.md
    
    # Replace changelog
    mv /tmp/changelog_new.md CHANGELOG.md
fi

# Build the package to verify
echo -e "${YELLOW}Building package...${NC}"
pdm build

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
pdm run test || {
    echo -e "${RED}Tests failed! Aborting release.${NC}"
    exit 1
}

# Git operations
echo -e "${YELLOW}Committing changes...${NC}"
git add pyproject.toml CHANGELOG.md src/claude_code_trees/__init__.py
git commit -m "Release v$NEW_VERSION"

# Create tag
echo -e "${YELLOW}Creating tag v$NEW_VERSION...${NC}"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo -e "${GREEN}✅ Release prepared successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the changes: git show"
echo "  2. Push to GitHub: git push && git push --tags"
echo "  3. Create release on GitHub: https://github.com/rizome-dev/claude-code-trees/releases/new"
echo "     - Tag: v$NEW_VERSION"
echo "     - Title: v$NEW_VERSION"
echo "     - Copy description from CHANGELOG.md"
echo "  4. The GitHub Action will automatically publish to PyPI"
echo ""
echo -e "${YELLOW}Or run: git push && git push --tags && gh release create v$NEW_VERSION --title \"v$NEW_VERSION\" --notes-file CHANGELOG.md${NC}"