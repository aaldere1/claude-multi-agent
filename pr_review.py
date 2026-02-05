#!/usr/bin/env python3
"""
PR-Aware Smart Review Tool

This tool:
1. Detects current branch and associated PR
2. Fetches PR description, comments, and review feedback
3. Gets CI/check status and any failures
4. Reviews uncommitted changes against ALL of that context
5. Verifies if previous issues were addressed and checks for new issues

Usage:
    # Auto-detect PR and review uncommitted changes
    python pr_review.py --repo /path/to/repo

    # With additional context about what was just done
    python pr_review.py --repo /path/to/repo --context "Fixed the memory leak issue"

    # Include conversation context from Cursor (pipe it in)
    echo "I fixed the retain cycle by adding weak self" | python pr_review.py --repo /path/to/repo
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from config_loader import load_project_config, build_review_prompt

load_dotenv()

BASE_PR_REVIEWER_PROMPT = """You are an expert code reviewer performing a PR readiness check.

You have access to:
1. The PR description (what this PR is supposed to accomplish)
2. Previous review comments (feedback that needs to be addressed)
3. CI/build status (any failures that need fixing)
4. The current uncommitted changes (what the developer just did)
5. What the developer says they did (their context)

## Your Task

**PRIMARY GOAL: Verify the changes address previous feedback and don't introduce new issues.**

Review in this order:
1. **PR Goal Check**: Do the uncommitted changes align with the PR's purpose?
2. **Review Comments Check**: Were previous reviewer comments addressed?
3. **CI/Build Check**: If there were failures, do these changes fix them?
4. **New Issues Check**: Do these changes introduce any new problems?
5. **Code Quality Check**: Best practices for the language/framework

## Response Format

Start with a status:
- **READY TO COMMIT** - All issues addressed, no new problems
- **NEEDS WORK** - Some issues remain or new problems found

Then provide sections:

### PR Alignment
[Does this change match the PR goal?]

### Previous Feedback Status
[For each review comment: ✅ Addressed / ❌ Not addressed / ⚠️ Partially addressed]

### CI/Build Issues
[Were any previous failures fixed? Any new ones likely?]

### New Issues Found
[Any problems introduced by these changes?]

### Recommendation
[What to do next - commit, or what to fix first]

Be specific. Reference line numbers from the diff. Be concise but thorough."""


def run_cmd(cmd: list[str], cwd: str = None) -> tuple[str, int]:
    """Run a command and return output and return code."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip(), result.returncode


def get_current_branch(repo_path: str) -> str:
    """Get the current git branch."""
    output, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    return output


def get_pr_for_branch(repo_path: str, branch: str) -> dict | None:
    """Get PR details for the current branch using gh CLI."""
    # Try to get PR number for this branch
    output, code = run_cmd([
        "gh", "pr", "view", branch,
        "--json", "number,title,body,state,reviews,comments,statusCheckRollup"
    ], repo_path)

    if code != 0:
        return None

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def get_pr_review_comments(repo_path: str, pr_number: int) -> list[dict]:
    """Get review comments on the PR."""
    output, code = run_cmd([
        "gh", "api",
        f"repos/:owner/:repo/pulls/{pr_number}/comments",
        "--jq", '[.[] | {body: .body, path: .path, line: .line, user: .user.login, state: .state}]'
    ], repo_path)

    if code != 0:
        return []

    try:
        return json.loads(output) if output else []
    except json.JSONDecodeError:
        return []


def get_pr_issue_comments(repo_path: str, pr_number: int) -> list[dict]:
    """Get issue-style comments on the PR."""
    output, code = run_cmd([
        "gh", "api",
        f"repos/:owner/:repo/issues/{pr_number}/comments",
        "--jq", '[.[] | {body: .body, user: .user.login}]'
    ], repo_path)

    if code != 0:
        return []

    try:
        return json.loads(output) if output else []
    except json.JSONDecodeError:
        return []


def get_ci_status(repo_path: str) -> list[dict]:
    """Get CI check status for the current branch."""
    output, code = run_cmd([
        "gh", "pr", "checks",
        "--json", "name,state,conclusion"
    ], repo_path)

    if code != 0:
        return []

    try:
        return json.loads(output) if output else []
    except json.JSONDecodeError:
        return []


def get_git_diff(repo_path: str, staged: bool = False) -> str:
    """Get git diff for uncommitted changes."""
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    output, _ = run_cmd(cmd, repo_path)
    return output


def get_changed_files(repo_path: str) -> list[str]:
    """Get list of changed files."""
    output, _ = run_cmd(["git", "diff", "--name-only"], repo_path)
    return [f for f in output.split('\n') if f]


def format_pr_context(pr_data: dict, review_comments: list, issue_comments: list, ci_status: list) -> str:
    """Format all PR context into a readable string."""
    parts = []

    # PR Info
    parts.append(f"## PR #{pr_data.get('number')}: {pr_data.get('title')}")
    if pr_data.get('body'):
        parts.append(f"\n### PR Description\n{pr_data['body']}")

    # Review comments (code-specific feedback)
    if review_comments:
        parts.append("\n### Code Review Comments (to address)")
        for i, comment in enumerate(review_comments, 1):
            path = comment.get('path', 'general')
            line = comment.get('line', '')
            line_info = f" (line {line})" if line else ""
            parts.append(f"{i}. **{path}{line_info}**: {comment.get('body', '')[:500]}")

    # Issue comments (general discussion)
    if issue_comments:
        parts.append("\n### PR Discussion Comments")
        for comment in issue_comments[-5:]:  # Last 5 comments
            parts.append(f"- @{comment.get('user', 'unknown')}: {comment.get('body', '')[:300]}")

    # CI Status
    if ci_status:
        failed = [c for c in ci_status if c.get('conclusion') == 'failure']
        if failed:
            parts.append("\n### CI Failures (need fixing)")
            for check in failed:
                parts.append(f"- ❌ {check.get('name')}")
        else:
            parts.append("\n### CI Status: ✅ All checks passing")

    return "\n".join(parts)


def review_with_pr_context(
    diff: str,
    pr_context: str,
    files_changed: list[str],
    developer_context: str = None,
    project_config: dict = None
) -> str:
    """Send everything to the reviewer."""
    client = anthropic.Anthropic()

    # Build system prompt with project-specific context
    if project_config:
        system_prompt = build_review_prompt(project_config, BASE_PR_REVIEWER_PROMPT)
    else:
        system_prompt = BASE_PR_REVIEWER_PROMPT

    prompt_parts = []

    if pr_context:
        prompt_parts.append(pr_context)

    if developer_context:
        prompt_parts.append(f"\n## What The Developer Says They Did\n{developer_context}")

    prompt_parts.append(f"\n## Files With Uncommitted Changes\n" + "\n".join(f"- {f}" for f in files_changed))
    prompt_parts.append(f"\n## Current Uncommitted Changes (git diff)\n```diff\n{diff}\n```")

    prompt = "\n".join(prompt_parts)

    response = client.messages.create(
        model=os.getenv("DEFAULT_MODEL", "claude-opus-4-6"),
        max_tokens=3000,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="PR-aware smart code review")
    parser.add_argument("--repo", "-r", required=True, help="Path to git repository")
    parser.add_argument("--context", "-c", help="What you just did (optional)")
    parser.add_argument("--staged", "-s", action="store_true", help="Review staged changes only")
    parser.add_argument("--copy", action="store_true", help="Copy result to clipboard")

    args = parser.parse_args()
    repo_path = os.path.expanduser(args.repo)

    # Get context from stdin if available
    developer_context = args.context
    if not developer_context and not sys.stdin.isatty():
        developer_context = sys.stdin.read().strip()

    # Get current branch
    branch = get_current_branch(repo_path)
    print(f"🌿 Branch: {branch}")

    # Get PR info
    pr_data = get_pr_for_branch(repo_path, branch)
    pr_context = ""

    if pr_data:
        pr_number = pr_data.get('number')
        print(f"🔗 PR #{pr_number}: {pr_data.get('title')}")

        # Get all PR context
        review_comments = get_pr_review_comments(repo_path, pr_number)
        issue_comments = get_pr_issue_comments(repo_path, pr_number)
        ci_status = get_ci_status(repo_path)

        if review_comments:
            print(f"💬 {len(review_comments)} review comment(s) to address")
        if ci_status:
            failed = [c for c in ci_status if c.get('conclusion') == 'failure']
            if failed:
                print(f"❌ {len(failed)} CI check(s) failing")
            else:
                print("✅ CI checks passing")

        pr_context = format_pr_context(pr_data, review_comments, issue_comments, ci_status)
    else:
        print("ℹ️  No PR found for this branch (reviewing without PR context)")

    # Load project config
    project_config = load_project_config(repo_path)
    if project_config.get("name") != "Project":
        print(f"📦 Project: {project_config.get('name')}")

    # Get the diff
    diff = get_git_diff(repo_path, args.staged)

    if not diff.strip():
        print("\n⚠️  No uncommitted changes found.")
        print("Make your changes first, then run this review before committing.")
        sys.exit(0)

    files_changed = get_changed_files(repo_path)
    print(f"📝 Changed files: {', '.join(files_changed)}")

    if developer_context:
        print(f"💭 Context: {developer_context[:80]}...")

    print("\n" + "━" * 60)
    print("🔍 Analyzing changes against PR context...")
    print("━" * 60 + "\n")

    # Get the review
    review = review_with_pr_context(diff, pr_context, files_changed, developer_context, project_config)
    print(review)

    print("\n" + "━" * 60)

    if args.copy:
        subprocess.run(['pbcopy'], input=review.encode(), check=True)
        print("(Copied to clipboard)")

    # Exit code
    if "READY TO COMMIT" in review:
        print("✅ Ready to commit!")
        sys.exit(0)
    else:
        print("⚠️  Needs work before committing")
        sys.exit(1)


if __name__ == "__main__":
    main()
