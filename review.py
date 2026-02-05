#!/usr/bin/env python3
"""
Quick Review Tool - Send code/files to reviewer agent and get instant feedback.

Usage:
    # Review clipboard content
    python review.py --clipboard

    # Review a file
    python review.py --file path/to/file.swift

    # Review with a question
    python review.py --file path/to/file.swift --question "Is this thread-safe?"

    # Review stdin (pipe from pbpaste, etc)
    pbpaste | python review.py
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

BASE_REVIEWER_PROMPT = """You are an expert code reviewer.

Your role:
- Review code thoroughly but efficiently
- Focus on: bugs, memory issues, thread safety, best practices
- Be specific with line numbers or code references

Response format:
1. Start with **APPROVED** or **CHANGES_REQUESTED**
2. List specific issues (if any) with line references
3. Keep it actionable and concise
4. Max 5 issues per review - prioritize the most important"""


def get_clipboard():
    """Get content from macOS clipboard."""
    try:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout
    except:
        return None


def review_code(code: str, question: str = None, project_config: dict = None) -> str:
    """Send code to reviewer and get feedback."""
    client = anthropic.Anthropic()

    # Build system prompt with project-specific context
    if project_config:
        system = build_review_prompt(project_config, BASE_REVIEWER_PROMPT)
    else:
        system = BASE_REVIEWER_PROMPT

    prompt = f"Review this code:\n\n```\n{code}\n```"
    if question:
        prompt += f"\n\nSpecific question: {question}"

    response = client.messages.create(
        model=os.getenv("DEFAULT_MODEL", "claude-opus-4-6"),
        max_tokens=2048,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Quick code review tool")
    parser.add_argument("--file", "-f", help="File to review")
    parser.add_argument("--clipboard", "-c", action="store_true", help="Review clipboard content")
    parser.add_argument("--question", "-q", help="Specific question about the code")
    parser.add_argument("--repo", "-r", help="Repository path for loading project config")
    parser.add_argument("--copy", action="store_true", help="Copy result to clipboard")

    args = parser.parse_args()

    # Load project config if repo specified
    project_config = None
    if args.repo:
        project_config = load_project_config(os.path.expanduser(args.repo))
        if project_config.get("name") != "Project":
            print(f"📦 Project: {project_config.get('name')}")

    # Get code to review
    code = None

    if args.file:
        path = Path(args.file)
        if path.exists():
            code = path.read_text()
            print(f"Reviewing: {path}")
        else:
            print(f"File not found: {path}")
            sys.exit(1)
    elif args.clipboard:
        code = get_clipboard()
        if not code:
            print("Clipboard is empty")
            sys.exit(1)
        print("Reviewing clipboard content...")
    elif not sys.stdin.isatty():
        code = sys.stdin.read()
        print("Reviewing stdin...")
    else:
        print("No input provided. Use --file, --clipboard, or pipe content.")
        parser.print_help()
        sys.exit(1)

    # Get review
    print("-" * 50)
    review = review_code(code, args.question, project_config)
    print(review)
    print("-" * 50)

    # Copy to clipboard if requested
    if args.copy:
        subprocess.run(['pbcopy'], input=review.encode(), check=True)
        print("(Copied to clipboard)")

    # Exit code based on approval
    sys.exit(0 if "APPROVED" in review else 1)


if __name__ == "__main__":
    main()
