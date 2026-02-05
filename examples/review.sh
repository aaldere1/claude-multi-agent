#!/bin/bash
# PR-Aware Smart Review for your project
#
# Copy this to your project's scripts/ directory and update REPO path.
#
# Usage:
#   ./scripts/review.sh                           # Full PR-aware review
#   ./scripts/review.sh "I fixed the memory leak" # With context about what you did
#   ./scripts/review.sh --simple                  # Simple review (no PR context)

cd ~/claude-multi-agent
source venv/bin/activate

# UPDATE THIS to your project's path
REPO="/path/to/your/project"

if [ "$1" == "--simple" ]; then
    shift
    echo "Running simple review (no PR context)..."
    python smart_review.py --repo "$REPO" --context "$1"
elif [ -n "$1" ]; then
    echo "Running PR-aware review with context..."
    python pr_review.py --repo "$REPO" --context "$1"
else
    echo "Running full PR-aware review..."
    python pr_review.py --repo "$REPO"
fi
