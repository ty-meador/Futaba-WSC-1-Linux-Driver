#!/bin/bash
# prep-release.sh - Prepare a new release by updating version and creating git tag

set -e  # Exit on error

PYPROJECT="pyproject.toml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Helper functions
error() {
    echo "Error: $1" >&2
    exit 1
}

# Ensure we're in project root
cd "$PROJECT_ROOT"

# Check if pyproject.toml exists
[ -f "$PYPROJECT" ] || error "pyproject.toml not found in $PROJECT_ROOT"

# Check if git repo
git rev-parse --git-dir > /dev/null 2>&1 || error "Not a git repository"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Warning: You have uncommitted changes:"
    git status --short
    echo ""
    read -p "Continue anyway? (yes/no): " continue_dirty
    [ "$continue_dirty" = "yes" ] || error "Release cancelled. Commit or stash changes first."
    echo ""
fi

# Get current version from pyproject.toml
CURRENT_VERSION=$(tools/util.py --pyproject project.version 2>/dev/null)
[ -n "$CURRENT_VERSION" ] || error "Could not read current version from pyproject.toml"

echo "Current version: $CURRENT_VERSION"
echo ""

# Get next version from user
while true; do
    read -p "Enter next version: " NEXT_VERSION
    
    # Validate input is not empty
    if [ -z "$NEXT_VERSION" ]; then
        error "Version cannot be empty"
    fi
    
    # Validate semantic version format (X.Y.Z)
    if ! echo "$NEXT_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        error "Version must be in format X.Y.Z (e.g., 1.2.3)"
    fi
    
    # Check if version is the same
    if [ "$NEXT_VERSION" = "$CURRENT_VERSION" ]; then
        error "New version must be different from current version"
    fi
    
    # Check if tag already exists
    if git rev-parse "release/$NEXT_VERSION" >/dev/null 2>&1; then
        error "Tag release/$NEXT_VERSION already exists"
    fi
    
    # All validations passed
    break
done

echo ""
echo "Release Summary"
echo ""
echo "  Current version: $CURRENT_VERSION"
echo "  Next version:    $NEXT_VERSION"
echo "  Tag:             release/$NEXT_VERSION"
echo ""
echo "This will:"
echo "  1. Update pyproject.toml version"
echo "  2. Commit the change"
echo "  3. Create git tag release/$NEXT_VERSION"
echo ""

# Final confirmation
read -p "Continue? (yes/no): " CONFIRM
[ "$CONFIRM" = "yes" ] || error "Release cancelled"

echo ""
echo "Updating version in pyproject.toml..."


# Update version in pyproject.toml
tools/utils.py --pyproject project.version=${NEXT_VERSION}

# Verify the change
NEW_VERSION_CHECK=$(tools/util.py --pyproject project.version)
if [ "$NEW_VERSION_CHECK" != "$NEXT_VERSION" ]; then
    error "Version update verification failed. Expected $NEXT_VERSION, got $NEW_VERSION_CHECK"
fi

echo "Version updated: $CURRENT_VERSION -> $NEXT_VERSION"
echo ""

# Git operations
echo "Committing changes..."
git add "$PYPROJECT"
git commit -m "Bump version to $NEXT_VERSION"
echo "Changes committed"
echo ""

echo "Creating tag..."
git tag -a "release/$NEXT_VERSION" -m "Release version $NEXT_VERSION"
echo "Tag created: release/$NEXT_VERSION"
echo ""

echo "Release preparation complete"
echo ""
echo "Next steps:"
echo "  1. Run: make all"
echo "  2. Test the build"
echo "  3. Push changes: git push && git push --tags"
echo ""