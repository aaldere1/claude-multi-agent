#!/usr/bin/env python3
"""
Multi-Agent Orchestrator for Autonomous Code Development

This orchestrator manages a conversation between a Developer agent and a Reviewer agent,
iterating until the code is approved or max iterations are reached.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-opus-4-6")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))

# Agent System Prompts
DEVELOPER_SYSTEM_PROMPT = """You are a senior software developer. Your role is to write clean, well-documented, production-ready code.

Guidelines:
- Write code that is readable and maintainable
- Follow best practices for the language/framework
- Include appropriate error handling
- Add comments only where logic isn't self-evident
- Consider edge cases

When responding to reviewer feedback:
- Address each point specifically
- Explain your changes
- Ask clarifying questions if feedback is unclear

Output format:
1. Brief explanation of your approach
2. The code (in appropriate code blocks)
3. Any notes or caveats"""

REVIEWER_SYSTEM_PROMPT = """You are a strict but constructive code reviewer. Your role is to ensure code quality before it reaches production.

Review criteria:
- Correctness: Does it solve the problem?
- Bugs: Any logic errors, off-by-one errors, null pointer issues?
- Security: Any vulnerabilities (injection, XSS, etc.)?
- Performance: Any obvious inefficiencies?
- Readability: Is the code clear and well-organized?
- Best practices: Does it follow language/framework conventions?

Response format:
Start with either:
- "APPROVED" - if the code is production-ready
- "CHANGES_REQUESTED" - if improvements are needed

If CHANGES_REQUESTED, provide:
1. Numbered list of specific issues
2. For each issue: what's wrong and how to fix it
3. Priority (critical/important/minor) for each issue

Be specific and actionable. Don't be vague."""

IOS_DEVELOPER_SYSTEM_PROMPT = """You are a senior iOS developer specializing in Swift and SwiftUI.

Guidelines:
- Write modern Swift code (Swift 5.9+)
- Use SwiftUI best practices
- Proper state management (@State, @Binding, @ObservedObject, @StateObject)
- Follow Apple Human Interface Guidelines
- Consider accessibility (VoiceOver, Dynamic Type)
- Handle errors gracefully
- Use async/await for asynchronous code

Output format:
1. Brief explanation of your approach
2. The Swift code (in ```swift code blocks)
3. Any notes about integration or usage"""

IOS_REVIEWER_SYSTEM_PROMPT = """You are a senior iOS code reviewer specializing in Swift and SwiftUI.

Review criteria:
- Memory management: Check for retain cycles, proper use of weak/unowned
- Main thread: UI updates must be on main thread
- State management: Proper use of @State, @Binding, @ObservedObject
- Performance: Avoid unnecessary view updates, use lazy loading
- Accessibility: VoiceOver labels, Dynamic Type support
- Error handling: Proper do-catch, Result types, optionals
- API design: Clear interfaces, good naming
- SwiftUI idioms: Prefer declarative over imperative

Response format:
Start with either:
- "APPROVED" - if the code is production-ready for iOS
- "CHANGES_REQUESTED" - if improvements are needed

Be specific about iOS/Swift issues. Reference Apple documentation when relevant."""


class Agent:
    """Represents a Claude agent with a specific role."""

    def __init__(self, name: str, system_prompt: str, model: str = DEFAULT_MODEL):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.client = anthropic.Anthropic()

    def respond(self, messages: list[dict], temperature: float = 0.3) -> str:
        """Get a response from this agent."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=self.system_prompt,
            messages=messages
        )
        return response.content[0].text


class Orchestrator:
    """Manages the multi-agent development loop."""

    def __init__(self, context_type: str = "general", verbose: bool = True):
        self.verbose = verbose
        self.conversation_log = []

        # Select agent prompts based on context
        if context_type == "ios":
            dev_prompt = IOS_DEVELOPER_SYSTEM_PROMPT
            rev_prompt = IOS_REVIEWER_SYSTEM_PROMPT
        else:
            dev_prompt = DEVELOPER_SYSTEM_PROMPT
            rev_prompt = REVIEWER_SYSTEM_PROMPT

        self.developer = Agent("Developer", dev_prompt)
        self.reviewer = Agent("Reviewer", rev_prompt, model=DEFAULT_MODEL)

    def log(self, message: str):
        """Log a message if verbose mode is on."""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run(self, task: str, file_context: Optional[str] = None, max_iterations: int = MAX_ITERATIONS) -> dict:
        """
        Run the developer-reviewer loop.

        Returns:
            dict with keys: success, iterations, final_code, conversation_log
        """
        self.log(f"Starting autonomous loop for task: {task[:50]}...")

        # Build initial prompt
        initial_prompt = f"Task: {task}"
        if file_context:
            initial_prompt += f"\n\nExisting code context:\n```\n{file_context}\n```"

        developer_messages = [{"role": "user", "content": initial_prompt}]
        iteration = 0
        final_code = None

        while iteration < max_iterations:
            iteration += 1
            self.log(f"\n{'='*50}")
            self.log(f"Iteration {iteration}/{max_iterations}")

            # Developer turn
            self.log("Developer is working...")
            dev_response = self.developer.respond(developer_messages)
            self.conversation_log.append({
                "agent": "developer",
                "iteration": iteration,
                "content": dev_response
            })

            if self.verbose:
                print(f"\n--- Developer Response ---\n{dev_response[:500]}{'...' if len(dev_response) > 500 else ''}\n")

            # Reviewer turn
            self.log("Reviewer is analyzing...")
            reviewer_messages = [{
                "role": "user",
                "content": f"Review this code submission:\n\n{dev_response}"
            }]
            rev_response = self.reviewer.respond(reviewer_messages, temperature=0.2)
            self.conversation_log.append({
                "agent": "reviewer",
                "iteration": iteration,
                "content": rev_response
            })

            if self.verbose:
                print(f"\n--- Reviewer Response ---\n{rev_response[:500]}{'...' if len(rev_response) > 500 else ''}\n")

            # Check if approved
            if rev_response.strip().upper().startswith("APPROVED"):
                self.log("Code APPROVED!")
                final_code = dev_response
                return {
                    "success": True,
                    "iterations": iteration,
                    "final_code": final_code,
                    "conversation_log": self.conversation_log
                }

            # Prepare feedback for next iteration
            developer_messages.append({"role": "assistant", "content": dev_response})
            developer_messages.append({
                "role": "user",
                "content": f"The reviewer has requested changes:\n\n{rev_response}\n\nPlease address this feedback and provide an updated implementation."
            })

            self.log("Changes requested, continuing to next iteration...")

        # Max iterations reached
        self.log(f"Max iterations ({max_iterations}) reached without approval")
        return {
            "success": False,
            "iterations": iteration,
            "final_code": dev_response,  # Last attempt
            "conversation_log": self.conversation_log,
            "note": "Max iterations reached - human review recommended"
        }


def load_file_context(file_paths: list[str]) -> str:
    """Load content from specified files."""
    context_parts = []
    for path in file_paths:
        p = Path(path)
        if p.exists():
            content = p.read_text()
            context_parts.append(f"// File: {path}\n{content}")
    return "\n\n".join(context_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Run autonomous developer-reviewer loop"
    )
    parser.add_argument(
        "--task", "-t",
        required=True,
        help="The development task to accomplish"
    )
    parser.add_argument(
        "--files", "-f",
        nargs="*",
        help="File paths to include as context"
    )
    parser.add_argument(
        "--context-type", "-c",
        choices=["general", "ios"],
        default="general",
        help="Type of development context (affects agent prompts)"
    )
    parser.add_argument(
        "--max-iterations", "-m",
        type=int,
        default=MAX_ITERATIONS,
        help=f"Maximum iterations before stopping (default: {MAX_ITERATIONS})"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for final code"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )

    args = parser.parse_args()

    # Load file context if provided
    file_context = None
    if args.files:
        file_context = load_file_context(args.files)

    # Run orchestrator
    orchestrator = Orchestrator(
        context_type=args.context_type,
        verbose=not args.quiet
    )

    result = orchestrator.run(
        task=args.task,
        file_context=file_context,
        max_iterations=args.max_iterations
    )

    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "="*60)
        if result["success"]:
            print(f"SUCCESS after {result['iterations']} iteration(s)")
        else:
            print(f"INCOMPLETE after {result['iterations']} iteration(s)")
            print(f"Note: {result.get('note', 'Human review recommended')}")
        print("="*60)
        print("\nFinal Code:\n")
        print(result["final_code"])

    # Save to file if requested
    if args.output:
        Path(args.output).write_text(result["final_code"])
        print(f"\nSaved to {args.output}")

    # Exit with appropriate code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
