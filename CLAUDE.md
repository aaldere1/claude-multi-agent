# CLAUDE.md - Multi-Agent Orchestrator

A system for autonomous code development using multiple Claude agents that collaborate.

## Project Overview

This project enables multiple Claude "agents" (with different personas/roles) to work together autonomously:
- **Developer Agent**: Writes code based on tasks
- **Reviewer Agent**: Reviews code and provides feedback
- **Orchestrator**: Manages the loop until code is approved

## Primary Use Case: Cursor IDE + PR-Aware Review

The main workflow integrates with Cursor IDE for iOS development:

1. Code in Cursor (make changes, don't commit)
2. Say `smart review` or `local review` in Cursor chat
3. External Claude reviewer checks your changes against PR context
4. Get verdict: READY TO COMMIT or NEEDS WORK

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# PR-aware review (recommended)
python pr_review.py --repo /path/to/project

# Simple git diff review
python smart_review.py --repo /path/to/project

# Quick file review
python review.py --file path/to/file.swift

# Run developer/reviewer loop
python orchestrator.py --task "Your task here" --context-type ios

# Start API server
python server.py
```

## Key Files

| File | Purpose |
|------|---------|
| `pr_review.py` | **PR-aware review** - fetches GitHub PR context, reviews uncommitted changes |
| `smart_review.py` | Git diff review - reviews changes without PR context |
| `review.py` | Quick file/clipboard review |
| `orchestrator.py` | Full developer/reviewer loop for autonomous coding |
| `server.py` | FastAPI server for HTTP access |
| `config/agents.yaml` | Agent personas and system prompts |

## Cursor Integration

Projects using this system need:
1. `scripts/review.sh` - wrapper that calls the Python tools
2. `.cursor/rules/peer-review.mdc` - Cursor rule with trigger words

Example integration: `/Users/aaldere1/CineConcerts-App-ios26/`

## Usage Examples

```bash
# iOS development task
python orchestrator.py -t "Add pull-to-refresh to the list view" -c ios

# With file context
python orchestrator.py -t "Fix the bug" -f path/to/file.swift -c ios

# Output to file
python orchestrator.py -t "Create a login form" -c ios -o output.swift

# JSON output (for scripts)
python orchestrator.py -t "..." --json --quiet
```

## API Endpoints

When running `server.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/orchestrate` | POST | Start async task |
| `/api/orchestrate/sync` | POST | Run synchronously |
| `/api/task/{id}` | GET | Get task status |
| `/api/tasks` | GET | List all tasks |

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Required
DEFAULT_MODEL=claude-sonnet-4-20250514
MAX_ITERATIONS=5
```

## Cursor Integration

See `docs/cursor-integration.md` for setting up custom commands like `/review-loop` and `/ios-review`.

## Architecture

```
User Task
    │
    ▼
┌─────────────────┐
│  Orchestrator   │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
Developer  Reviewer
  Agent      Agent
    │         │
    └────┬────┘
         │
    Loop until
    APPROVED
         │
         ▼
   Final Code
```

## Extending

1. **Add new agent types**: Edit `config/agents.yaml`
2. **Add new context types**: Update prompts in `orchestrator.py`
3. **Custom workflows**: Create new orchestrator classes
