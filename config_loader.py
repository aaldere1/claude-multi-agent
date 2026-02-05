#!/usr/bin/env python3
"""
Config Loader for Project-Specific Review Settings

Loads project configuration from .claude-review.yaml in the target repository.
Falls back to sensible defaults if no config exists.
"""

import os
from pathlib import Path
from typing import Optional

import yaml


DEFAULT_CONFIG = {
    "name": "Project",
    "language": "general",
    "patterns": [],
    "review_focus": [
        "Code quality and best practices",
        "Error handling",
        "Performance considerations",
        "Security issues"
    ]
}

LANGUAGE_DEFAULTS = {
    "swift": {
        "review_focus": [
            "Memory management (retain cycles, weak/unowned)",
            "Threading (MainActor, async/await patterns)",
            "SwiftUI state management (@State, @Binding, @Observable)",
            "Error handling (no force unwraps)",
            "Performance (unnecessary view rebuilds)"
        ]
    },
    "python": {
        "review_focus": [
            "Type hints and documentation",
            "Error handling and edge cases",
            "Performance and efficiency",
            "Security (input validation, injection)"
        ]
    },
    "typescript": {
        "review_focus": [
            "Type safety and proper typing",
            "Null/undefined handling",
            "Async/await patterns",
            "React hooks rules (if applicable)"
        ]
    },
    "javascript": {
        "review_focus": [
            "Error handling",
            "Async patterns (promises, callbacks)",
            "Security (XSS, injection)",
            "Performance"
        ]
    }
}


def load_project_config(repo_path: str) -> dict:
    """
    Load project configuration from .claude-review.yaml in the repo.

    Args:
        repo_path: Path to the git repository

    Returns:
        Configuration dictionary with project settings
    """
    config_path = Path(repo_path) / ".claude-review.yaml"

    # Start with defaults
    config = DEFAULT_CONFIG.copy()

    # Try to load project-specific config
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                project_config = yaml.safe_load(f) or {}

            # Merge with defaults
            config.update(project_config)

        except Exception as e:
            print(f"Warning: Could not load {config_path}: {e}")

    # Apply language-specific defaults if not overridden
    language = config.get("language", "general")
    if language in LANGUAGE_DEFAULTS and "patterns" not in config:
        lang_defaults = LANGUAGE_DEFAULTS[language]
        for key, value in lang_defaults.items():
            if key not in config or not config[key]:
                config[key] = value

    return config


def build_review_prompt(config: dict, base_prompt: str) -> str:
    """
    Build a complete review prompt by injecting project-specific context.

    Args:
        config: Project configuration dictionary
        base_prompt: The base reviewer system prompt

    Returns:
        Complete system prompt with project context
    """
    prompt_parts = [base_prompt]

    # Add project name
    if config.get("name") and config["name"] != "Project":
        prompt_parts.append(f"\n## Project: {config['name']}")

    # Add language context
    if config.get("language") and config["language"] != "general":
        prompt_parts.append(f"\nLanguage/Framework: {config['language']}")

    # Add project-specific patterns
    if config.get("patterns"):
        prompt_parts.append("\n## Project-Specific Patterns")
        for pattern in config["patterns"]:
            prompt_parts.append(f"- {pattern}")

    # Add review focus areas
    if config.get("review_focus"):
        prompt_parts.append("\n## Review Focus Areas")
        for focus in config["review_focus"]:
            prompt_parts.append(f"- {focus}")

    return "\n".join(prompt_parts)


def get_tool_path() -> str:
    """
    Get the path to the claude-review-agent tool installation.

    Checks CLAUDE_REVIEW_HOME environment variable first,
    then falls back to common locations.
    """
    # Check environment variable
    env_path = os.environ.get("CLAUDE_REVIEW_HOME")
    if env_path and Path(env_path).exists():
        return env_path

    # Check common locations
    home = Path.home()
    common_paths = [
        home / "claude-review-agent",
        home / "cursor-review-agent",
        home / "claude-multi-agent",
        home / ".claude-review-agent",
    ]

    for path in common_paths:
        if path.exists() and (path / "pr_review.py").exists():
            return str(path)

    # Return current directory as fallback
    return str(Path(__file__).parent)
