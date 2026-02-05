#!/bin/bash
# PR-Aware Smart Review Script
#
# Copy this to your project's scripts/ directory.
# Make sure to set CLAUDE_REVIEW_HOME in your shell profile.
#
# Usage:
#   ./scripts/review.sh                           # Full PR-aware review
#   ./scripts/review.sh "I fixed the memory leak" # With context
#   ./scripts/review.sh --simple                  # Simple review (no PR context)

# Find the tool installation
if [ -n "$CLAUDE_REVIEW_HOME" ]; then
    TOOL_DIR="$CLAUDE_REVIEW_HOME"
elif [ -d "$HOME/claude-review-agent" ]; then
    TOOL_DIR="$HOME/claude-review-agent"
elif [ -d "$HOME/cursor-review-agent" ]; then
    TOOL_DIR="$HOME/cursor-review-agent"
else
    echo "❌ Could not find claude-review-agent installation."
    echo "Please set CLAUDE_REVIEW_HOME environment variable."
    echo ""
    echo "Example: Add to ~/.zshrc:"
    echo "  export CLAUDE_REVIEW_HOME=~/claude-review-agent"
    exit 1
fi

# Activate virtual environment
cd "$TOOL_DIR"
source venv/bin/activate

# Get the repo path (directory containing this script's parent)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"

# Run the appropriate review
if [ "$1" == "--simple" ]; then
    shift
    echo "🔍 Running simple review (no PR context)..."
    python smart_review.py --repo "$REPO" --context "$1"
elif [ -n "$1" ]; then
    echo "🔍 Running PR-aware review with context..."
    python pr_review.py --repo "$REPO" --context "$1"
else
    echo "🔍 Running full PR-aware review..."
    python pr_review.py --repo "$REPO"
fi
