#!/usr/bin/env python3
"""
File Watcher for Cursor ↔ Reviewer Agent Communication

This script watches a conversation file. When Cursor's AI writes to it,
the reviewer agent automatically analyzes and appends feedback.

Usage:
    python watcher.py [--file path/to/conversation.md]

Then in Cursor, tell Claude to write to that file with code/questions.
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Reviewer system prompt
REVIEWER_PROMPT = """You are an expert iOS code reviewer working alongside another AI developer in Cursor.

Your role:
- Review code changes written by the Cursor AI
- Provide specific, actionable feedback
- Be constructive but thorough

Response format:
1. Start with **APPROVED** or **CHANGES_REQUESTED**
2. If changes requested, list specific issues with line references
3. Keep feedback concise and actionable
4. End with encouragement if approved

Remember: You're collaborating, not competing. Help make the code production-ready."""


class ConversationWatcher:
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.client = anthropic.Anthropic()
        self.last_content = ""
        self.last_modified = 0

        # Create file if it doesn't exist
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.filepath.write_text(self._initial_content())
            print(f"Created conversation file: {self.filepath}")

    def _initial_content(self) -> str:
        return f"""# AI Collaboration Conversation

This file enables communication between Cursor AI and the Reviewer Agent.

## How to use:
1. In Cursor, tell Claude to write code/changes under a "## Cursor:" section
2. The reviewer agent will automatically respond under "## Reviewer:"
3. Continue the conversation until code is approved

---

## Cursor:
(Write your code or questions here)

"""

    def _extract_latest_cursor_message(self, content: str) -> str | None:
        """Extract the most recent Cursor message."""
        # Find all Cursor sections
        pattern = r'## Cursor:\s*\n(.*?)(?=## Reviewer:|## Cursor:|$)'
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            return matches[-1].strip()
        return None

    def _count_reviewer_responses(self, content: str) -> int:
        """Count how many reviewer responses exist."""
        return len(re.findall(r'## Reviewer:', content))

    def _count_cursor_messages(self, content: str) -> int:
        """Count how many cursor messages exist."""
        return len(re.findall(r'## Cursor:', content))

    def get_review(self, code_or_message: str) -> str:
        """Get reviewer feedback for the given content."""
        response = self.client.messages.create(
            model=os.getenv("DEFAULT_MODEL", "claude-opus-4-6"),
            max_tokens=2048,
            temperature=0.2,
            system=REVIEWER_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Review this from the Cursor AI:\n\n{code_or_message}"
            }]
        )
        return response.content[0].text

    def append_review(self, review: str):
        """Append reviewer response to the file."""
        content = self.filepath.read_text()
        timestamp = datetime.now().strftime("%H:%M:%S")

        new_content = content.rstrip() + f"\n\n## Reviewer: ({timestamp})\n{review}\n\n## Cursor:\n(Your response here)\n"
        self.filepath.write_text(new_content)

    def check_and_respond(self) -> bool:
        """Check for new Cursor messages and respond if needed."""
        try:
            stat = self.filepath.stat()
            if stat.st_mtime <= self.last_modified:
                return False

            self.last_modified = stat.st_mtime
            content = self.filepath.read_text()

            if content == self.last_content:
                return False

            # Check if there's a new Cursor message without a Reviewer response
            cursor_count = self._count_cursor_messages(content)
            reviewer_count = self._count_reviewer_responses(content)

            if cursor_count > reviewer_count:
                latest_message = self._extract_latest_cursor_message(content)
                if latest_message and latest_message != "(Write your code or questions here)" and latest_message != "(Your response here)":
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New message from Cursor detected...")
                    print(f"Message preview: {latest_message[:100]}...")
                    print("Getting review...")

                    review = self.get_review(latest_message)
                    self.append_review(review)

                    print(f"Review added! Status: {'APPROVED' if 'APPROVED' in review else 'CHANGES_REQUESTED'}")
                    return True

            self.last_content = content
            return False

        except Exception as e:
            print(f"Error: {e}")
            return False

    def watch(self, interval: float = 2.0):
        """Watch the file for changes."""
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║           Cursor ↔ Reviewer Agent Communication                 ║
╠══════════════════════════════════════════════════════════════════╣
║  Watching: {str(self.filepath):<52} ║
║  Interval: {interval}s                                              ║
╠══════════════════════════════════════════════════════════════════╣
║  INSTRUCTIONS:                                                   ║
║  1. Open the conversation file in Cursor                        ║
║  2. Tell Cursor AI to write code under "## Cursor:" sections    ║
║  3. This watcher will auto-respond with reviews                 ║
║  4. Continue until APPROVED                                      ║
╠══════════════════════════════════════════════════════════════════╣
║  Press Ctrl+C to stop                                            ║
╚══════════════════════════════════════════════════════════════════╝
""")

        try:
            while True:
                self.check_and_respond()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")


def main():
    parser = argparse.ArgumentParser(description="Watch for Cursor AI messages and respond with reviews")
    parser.add_argument(
        "--file", "-f",
        default=os.path.expanduser("~/claude-multi-agent/conversation.md"),
        help="Path to conversation file"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Check interval in seconds"
    )

    args = parser.parse_args()

    watcher = ConversationWatcher(args.file)
    watcher.watch(args.interval)


if __name__ == "__main__":
    main()
