#!/usr/bin/env python3
"""
Multi-Perspective Team Review Tool

Runs multiple specialized reviewer agents in parallel, each examining code
from a different angle, then synthesizes their findings into a unified report.

Default perspectives (iOS-focused):
1. iOS Architect - Swift patterns, MVVM/data flow, navigation, async/await
2. Apple Design & UX - HIG compliance, accessibility, animations, layouts
3. Bug Hunter - Retain cycles, force unwraps, race conditions, threading
4. Production Readiness - Error handling, edge cases, App Store, performance

Usage:
    # Team review with PR context
    python team_review.py --repo /path/to/project

    # With additional context
    python team_review.py --repo /path/to/project --context "Refactored navigation stack"
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
from dotenv import load_dotenv

from config_loader import load_project_config, build_review_prompt
from pr_review import (
    get_current_branch,
    get_pr_for_branch,
    get_pr_review_comments,
    get_pr_issue_comments,
    get_ci_status,
    format_pr_context,
    get_git_diff,
    get_changed_files,
)

load_dotenv()

# Default iOS-focused perspectives
DEFAULT_PERSPECTIVES = [
    {
        "name": "iOS Architect",
        "focus": (
            "Swift patterns, MVVM/data flow, @Observable state management, "
            "navigation architecture, dependency injection, async/await correctness, "
            "proper use of actors, protocol-oriented design"
        ),
        "system_prompt": """You are a senior iOS architect reviewing code changes.

Your focus areas:
- Swift/SwiftUI architectural patterns (MVVM, coordinator, repository)
- Data flow and @Observable/@State/@Binding state management
- Navigation architecture (NavigationStack, NavigationPath)
- Dependency injection and testability
- async/await correctness and structured concurrency
- Proper use of actors and actor isolation
- Protocol-oriented design
- Module boundaries and separation of concerns

Review the diff and identify architectural issues. Be specific with line references.
Focus ONLY on architecture - leave bugs, UX, and shipping concerns to other reviewers.

Response format:
1. Brief architectural assessment (1-2 sentences)
2. Issues found (numbered, with severity: critical/important/minor)
3. Each issue should reference specific lines from the diff"""
    },
    {
        "name": "Apple Design & UX",
        "focus": (
            "HIG compliance, accessibility (VoiceOver, Dynamic Type), "
            "animations, responsive layouts, Liquid Glass awareness, "
            "user experience quality"
        ),
        "system_prompt": """You are an Apple design and UX specialist reviewing code changes.

Your focus areas:
- Human Interface Guidelines (HIG) compliance
- Accessibility: VoiceOver labels, Dynamic Type support, accessibility traits
- Animation quality and appropriateness
- Responsive layouts across device sizes
- Liquid Glass / iOS 26 design language awareness
- Color and typography system usage
- Touch target sizes (minimum 44pt)
- Loading states, empty states, error states UX

Review the diff for UX and design issues. Be specific with line references.
Focus ONLY on design/UX - leave architecture, bugs, and shipping concerns to other reviewers.

Response format:
1. Brief UX assessment (1-2 sentences)
2. Issues found (numbered, with severity: critical/important/minor)
3. Each issue should reference specific lines from the diff"""
    },
    {
        "name": "Bug Hunter",
        "focus": (
            "Retain cycles, force unwraps, race conditions, nil handling, "
            "crash-prone patterns, threading safety (MainActor), memory leaks, "
            "off-by-one errors"
        ),
        "system_prompt": """You are a relentless bug hunter reviewing iOS code changes.

Your focus areas:
- Retain cycles (closure captures, delegate patterns)
- Force unwraps (!) that could crash
- Race conditions and data races
- Nil handling and optional chaining gaps
- Crash-prone patterns (index out of bounds, division by zero)
- Threading safety: MainActor violations, background thread UI updates
- Memory leaks (strong reference cycles, NotificationCenter observers)
- Off-by-one errors in collections/loops
- Unhandled error paths

Review the diff and find bugs. Be specific with line references.
Focus ONLY on bugs and crash risks - leave architecture, UX, and shipping concerns to other reviewers.
Your job is to find what others miss.

Response format:
1. Brief risk assessment (1-2 sentences)
2. Bugs/risks found (numbered, with severity: critical/important/minor)
3. Each issue should reference specific lines from the diff"""
    },
    {
        "name": "Production Readiness",
        "focus": (
            "Error handling coverage, edge cases, App Store requirements, "
            "performance (unnecessary view rebuilds, lazy loading), "
            "localization readiness, the 'would you ship this?' check"
        ),
        "system_prompt": """You are a production readiness reviewer - the last check before shipping.

Your focus areas:
- Error handling coverage: are all failure paths handled gracefully?
- Edge cases: empty states, nil data, network failures, large datasets
- App Store requirements: privacy, entitlements, required capabilities
- Performance: unnecessary view rebuilds, missing lazy loading, N+1 queries
- Localization readiness: hardcoded strings, RTL support
- Logging and debugging: appropriate log levels, no sensitive data logged
- The "would you ship this?" gut check

Review the diff with a shipping mindset. Be specific with line references.
Focus ONLY on production readiness - leave architecture, UX, and bug hunting to other reviewers.

Response format:
1. Ship/No-ship assessment (1-2 sentences)
2. Issues found (numbered, with severity: critical/important/minor)
3. Each issue should reference specific lines from the diff"""
    },
]

SYNTHESIS_PROMPT = """You are a lead reviewer synthesizing feedback from multiple specialized reviewers.

You received reviews from these perspectives:
{perspective_names}

Your task:
1. Read all reviews carefully
2. Deduplicate overlapping issues
3. Rank ALL issues by priority (critical first, then important, then minor)
4. Produce a unified verdict

Response format:

Start with:
- **APPROVED** - if no critical/important issues found across all reviews
- **CHANGES_REQUESTED** - if any critical or important issues exist

### Priority-Ranked Issues

List all unique issues in priority order:
1. [CRITICAL] Description (from: Perspective Name) - line reference
2. [IMPORTANT] Description (from: Perspective Name) - line reference
3. [MINOR] Description (from: Perspective Name) - line reference

### Summary by Perspective
Brief 1-line summary of each reviewer's assessment.

### Recommendation
What to address before committing (if anything)."""


def load_team_perspectives(project_config: dict) -> list[dict]:
    """
    Load team review perspectives from project config or use defaults.

    If the project's .claude-review.yaml has a team_perspectives key,
    those perspectives are used. Otherwise, returns the default iOS perspectives.
    """
    custom = project_config.get("team_perspectives")
    if custom and isinstance(custom, list):
        perspectives = []
        for p in custom:
            name = p.get("name", "Reviewer")
            focus = p.get("focus", "General code quality")
            system_prompt = p.get("system_prompt") or (
                f"You are a specialized code reviewer focused on: {focus}\n\n"
                f"Review the diff and identify issues in your focus area. "
                f"Be specific with line references.\n\n"
                f"Response format:\n"
                f"1. Brief assessment (1-2 sentences)\n"
                f"2. Issues found (numbered, with severity: critical/important/minor)\n"
                f"3. Each issue should reference specific lines from the diff"
            )
            perspectives.append({
                "name": name,
                "focus": focus,
                "system_prompt": system_prompt,
            })
        return perspectives
    return DEFAULT_PERSPECTIVES


def run_perspective_review(
    perspective: dict,
    diff: str,
    pr_context: str,
    files_changed: list[str],
    developer_context: str,
    project_config: dict,
) -> dict:
    """Run a single perspective review. Called in parallel."""
    client = anthropic.Anthropic()
    model = os.getenv("DEFAULT_MODEL", "claude-opus-4-6")

    # Build the user prompt
    prompt_parts = []
    if pr_context:
        prompt_parts.append(pr_context)
    if developer_context:
        prompt_parts.append(f"\n## Developer Context\n{developer_context}")
    prompt_parts.append(
        f"\n## Files Changed\n" + "\n".join(f"- {f}" for f in files_changed)
    )
    prompt_parts.append(f"\n## Git Diff\n```diff\n{diff}\n```")

    # Add project-specific context to system prompt
    system_prompt = perspective["system_prompt"]
    if project_config:
        system_prompt = build_review_prompt(project_config, system_prompt)

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
    )

    return {
        "name": perspective["name"],
        "focus": perspective["focus"],
        "review": response.content[0].text,
    }


def synthesize_reviews(reviews: list[dict], diff: str) -> str:
    """Combine all perspective reviews into a unified report."""
    client = anthropic.Anthropic()
    model = os.getenv("DEFAULT_MODEL", "claude-opus-4-6")

    perspective_names = ", ".join(r["name"] for r in reviews)
    system = SYNTHESIS_PROMPT.format(perspective_names=perspective_names)

    # Build the synthesis input
    parts = []
    for r in reviews:
        parts.append(f"## Review from: {r['name']}\nFocus: {r['focus']}\n\n{r['review']}")

    parts.append(f"\n## Original Diff (for reference)\n```diff\n{diff[:3000]}\n```")

    response = client.messages.create(
        model=model,
        max_tokens=3000,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": "\n\n---\n\n".join(parts)}],
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Multi-perspective team code review")
    parser.add_argument("--repo", "-r", required=True, help="Path to git repository")
    parser.add_argument("--context", "-c", help="What you just did (optional)")
    parser.add_argument("--staged", "-s", action="store_true", help="Review staged changes only")
    parser.add_argument("--copy", action="store_true", help="Copy result to clipboard")
    import subprocess

    args = parser.parse_args()
    repo_path = os.path.expanduser(args.repo)

    # Get context from stdin if available
    developer_context = args.context
    if not developer_context and not sys.stdin.isatty():
        developer_context = sys.stdin.read().strip()

    # Get current branch and PR info
    branch = get_current_branch(repo_path)
    print(f"🌿 Branch: {branch}")

    pr_data = get_pr_for_branch(repo_path, branch)
    pr_context = ""

    if pr_data:
        pr_number = pr_data.get("number")
        print(f"🔗 PR #{pr_number}: {pr_data.get('title')}")
        review_comments = get_pr_review_comments(repo_path, pr_number)
        issue_comments = get_pr_issue_comments(repo_path, pr_number)
        ci_status = get_ci_status(repo_path)
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

    # Load perspectives
    perspectives = load_team_perspectives(project_config)
    perspective_names = [p["name"] for p in perspectives]
    print(f"\n👥 Team Review: {', '.join(perspective_names)}")
    print("━" * 60)

    # Run all perspective reviews in parallel
    reviews = []
    with ThreadPoolExecutor(max_workers=len(perspectives)) as executor:
        future_to_name = {}
        for perspective in perspectives:
            future = executor.submit(
                run_perspective_review,
                perspective,
                diff,
                pr_context,
                files_changed,
                developer_context,
                project_config,
            )
            future_to_name[future] = perspective["name"]

        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                result = future.result()
                reviews.append(result)
                print(f"  ✅ {name} review complete")
            except Exception as e:
                print(f"  ❌ {name} review failed: {e}")

    if not reviews:
        print("\n❌ All reviews failed. Check your API key and network.")
        sys.exit(1)

    print(f"\n🔄 Synthesizing {len(reviews)} reviews...")
    print("━" * 60 + "\n")

    # Synthesize all reviews
    synthesis = synthesize_reviews(reviews, diff)
    print(synthesis)

    print("\n" + "━" * 60)

    # Print individual reviews in detail
    print("\n📋 Individual Perspective Reviews:")
    for r in reviews:
        print(f"\n{'─' * 40}")
        print(f"👤 {r['name']} ({r['focus'][:60]}...)")
        print(f"{'─' * 40}")
        print(r["review"])

    print("\n" + "━" * 60)

    if args.copy:
        subprocess.run(["pbcopy"], input=synthesis.encode(), check=True)
        print("(Synthesis copied to clipboard)")

    # Exit code based on synthesis verdict
    if "APPROVED" in synthesis and "CHANGES_REQUESTED" not in synthesis:
        print("✅ Team review: APPROVED")
        sys.exit(0)
    else:
        print("⚠️  Team review: Changes requested")
        sys.exit(1)


if __name__ == "__main__":
    main()
