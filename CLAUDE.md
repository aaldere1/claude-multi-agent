# CLAUDE.md - Claude Review Agent

AI-powered code review tool that integrates with Cursor IDE.

## Quick Reference

```bash
# Activate environment
source venv/bin/activate

# PR-aware review (recommended)
python pr_review.py --repo /path/to/project

# Simple review (no PR context)
python smart_review.py --repo /path/to/project

# Multi-perspective team review (4 specialized reviewers)
python team_review.py --repo /path/to/project

# Review single file
python review.py --file /path/to/file.swift
```

## Key Files

| File | Purpose |
|------|---------|
| `pr_review.py` | PR-aware review with GitHub context |
| `smart_review.py` | Git diff review without PR context |
| `team_review.py` | Multi-perspective team review (4 parallel reviewers) |
| `review.py` | Single file/clipboard review |
| `config_loader.py` | Loads project-specific configuration |

## Project Integration

Each project needs:
1. `scripts/review.sh` - Wrapper script (copy from `examples/`)
2. `.cursor/rules/peer-review.mdc` - Cursor rule (copy from `examples/`)
3. `.claude-review.yaml` - Optional project config

## Environment Variable

Set `CLAUDE_REVIEW_HOME` to point to this directory:
```bash
export CLAUDE_REVIEW_HOME=~/claude-review-agent
```

## Config File Format

Projects can have `.claude-review.yaml`:
```yaml
name: "Project Name"
language: swift
patterns:
  - "Pattern 1"
  - "Pattern 2"
```
