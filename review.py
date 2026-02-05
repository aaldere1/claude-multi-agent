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

load_dotenv()

REVIEWER_PROMPT = """You are an expert iOS/Swift code reviewer for a SwiftUI app.

Your role:
- Review code thoroughly but efficiently
- Focus on: bugs, memory issues, thread safety, SwiftUI best practices
- Be specific with line numbers or code references

Review criteria:
- Memory: Check for retain cycles (especially in closures), proper weak/unowned
- Threading: UI updates on MainActor, async/await patterns
- SwiftUI: Proper @State, @Binding, @Observable usage
- Performance: Unnecessary view rebuilds, lazy loading
- Error handling: No force unwraps, proper do-catch
- Code style: Clear naming, small functions, no TODOs

Response format:
1. Start with **APPROVED** or **CHANGES_REQUESTED**
2. List specific issues (if any) with line references
3. Keep it actionable and concise
4. Max 5 issues per review - prioritize the most important"""


CINECONCERTS_CONTEXT = """
This is the CineConcerts iOS app - a film music streaming and events app.

Key patterns in this codebase:
- Services are singletons with @MainActor isolation
- State management: @StateObject for view-owned, @EnvironmentObject for shared
- ImageCacheManager handles all image caching
- Firebase for auth, Firestore, and push notifications
- ShopifyService for e-commerce
- VimeoOTTService for video streaming
- Skeleton loaders with shimmer for loading states
- .liquidGlassBackground() modifier for consistent styling

Common issues to watch for:
- Not using @MainActor for UI state updates
- Missing error handling in async functions
- Not checking cache before network requests
- Force unwrapping optionals
"""


def get_clipboard():
    """Get content from macOS clipboard."""
    try:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout
    except:
        return None


def review_code(code: str, question: str = None, context: str = "ios") -> str:
    """Send code to reviewer and get feedback."""
    client = anthropic.Anthropic()

    # Build system prompt based on context
    system = REVIEWER_PROMPT
    if context == "cc" or context == "cineconcerts":
        system = REVIEWER_PROMPT + "\n\n" + CINECONCERTS_CONTEXT

    prompt = f"Review this code:\n\n```\n{code}\n```"
    if question:
        prompt += f"\n\nSpecific question: {question}"

    response = client.messages.create(
        model=os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514"),
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
    parser.add_argument("--context", "-x", choices=["ios", "cc", "general"], default="ios",
                        help="Context type: ios (default), cc (CineConcerts), general")
    parser.add_argument("--copy", action="store_true", help="Copy result to clipboard")

    args = parser.parse_args()

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
    review = review_code(code, args.question, args.context)
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
