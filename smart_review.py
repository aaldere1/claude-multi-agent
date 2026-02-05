#!/usr/bin/env python3
"""
Smart Review Tool - Reviews git changes with conversation context

This tool:
1. Uses `git diff` to find what actually changed
2. Accepts conversation context to understand intent
3. Reviews the changes in context of the task

Usage:
    # Review all uncommitted changes
    python smart_review.py --repo /path/to/repo

    # Review with conversation context (pipe from Cursor)
    echo "I was adding a refresh button to EventsListView" | python smart_review.py --repo /path/to/repo

    # Review specific files only
    python smart_review.py --repo /path/to/repo --files Main/Views/EventsListView.swift

    # Review with context file
    python smart_review.py --repo /path/to/repo --context-file /tmp/cursor_context.txt
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from config_loader import load_project_config, build_review_prompt

load_dotenv()

BASE_SMART_REVIEWER_PROMPT = """You are an expert code reviewer.

You are reviewing a git diff (the actual changes made, not entire files).

## Your Task
1. Understand what the developer was trying to accomplish (from the context provided)
2. Review ONLY the changes shown in the diff
3. Evaluate if the changes correctly implement the intended functionality
4. Check for best practices issues

## Response Format
Start with:
- **APPROVED** - Changes are good, accomplish the goal
- **CHANGES_REQUESTED** - Issues need to be addressed

Then provide:
1. Brief summary of what the changes do
2. List of issues (if any) - reference specific lines from the diff
3. Keep feedback actionable and specific

Be concise. Focus on the CHANGES, not hypothetical issues in unchanged code."""


def get_git_diff(repo_path: str, files: list[str] = None, staged: bool = False) -> str:
    """Get git diff for the repository."""
    cmd = ["git", "-C", repo_path, "diff"]
    if staged:
        cmd.append("--staged")
    if files:
        cmd.append("--")
        cmd.extend(files)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def get_changed_files(repo_path: str) -> list[str]:
    """Get list of changed files."""
    cmd = ["git", "-C", repo_path, "diff", "--name-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().split('\n')
    return [f for f in files if f]  # Filter empty strings


def get_staged_files(repo_path: str) -> list[str]:
    """Get list of staged files."""
    cmd = ["git", "-C", repo_path, "diff", "--staged", "--name-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().split('\n')
    return [f for f in files if f]


def review_diff(diff: str, context: str = None, files_changed: list[str] = None, project_config: dict = None) -> str:
    """Send diff to reviewer with context."""
    client = anthropic.Anthropic()

    # Build system prompt with project-specific context
    if project_config:
        system_prompt = build_review_prompt(project_config, BASE_SMART_REVIEWER_PROMPT)
    else:
        system_prompt = BASE_SMART_REVIEWER_PROMPT

    # Build the prompt
    prompt_parts = []

    if context:
        prompt_parts.append(f"## Developer Context\n{context}")

    if files_changed:
        prompt_parts.append(f"## Files Changed\n" + "\n".join(f"- {f}" for f in files_changed))

    prompt_parts.append(f"## Git Diff\n```diff\n{diff}\n```")

    prompt = "\n\n".join(prompt_parts)

    response = client.messages.create(
        model=os.getenv("DEFAULT_MODEL", "claude-opus-4-6"),
        max_tokens=2048,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Smart git-diff based code review")
    parser.add_argument("--repo", "-r", required=True, help="Path to git repository")
    parser.add_argument("--files", "-f", nargs="*", help="Specific files to review (optional)")
    parser.add_argument("--staged", "-s", action="store_true", help="Review staged changes only")
    parser.add_argument("--context", "-c", help="Context string explaining what was done")
    parser.add_argument("--context-file", help="File containing context")
    parser.add_argument("--copy", action="store_true", help="Copy result to clipboard")

    args = parser.parse_args()

    repo_path = os.path.expanduser(args.repo)

    # Get context from various sources
    context = args.context
    if args.context_file:
        context = Path(args.context_file).read_text()
    elif not sys.stdin.isatty():
        context = sys.stdin.read().strip()

    # Get the diff
    diff = get_git_diff(repo_path, args.files, args.staged)

    if not diff.strip():
        print("No changes detected. Nothing to review.")
        print("\nTip: Make sure you have uncommitted changes, or use --staged for staged changes.")
        sys.exit(0)

    # Load project config
    project_config = load_project_config(repo_path)
    if project_config.get("name") != "Project":
        print(f"📦 Project: {project_config.get('name')}")

    # Get list of changed files for context
    if args.staged:
        files_changed = get_staged_files(repo_path)
    else:
        files_changed = args.files or get_changed_files(repo_path)

    print(f"📋 Reviewing changes in: {', '.join(files_changed)}")
    if context:
        print(f"📝 Context: {context[:100]}{'...' if len(context) > 100 else ''}")
    print("━" * 50)

    # Get review
    review = review_diff(diff, context, files_changed, project_config)
    print(review)
    print("━" * 50)

    # Copy to clipboard if requested
    if args.copy:
        subprocess.run(['pbcopy'], input=review.encode(), check=True)
        print("(Copied to clipboard)")

    # Exit code based on approval
    sys.exit(0 if "APPROVED" in review else 1)


if __name__ == "__main__":
    main()
