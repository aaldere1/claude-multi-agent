# CLAUDE.md - Multi-Agent Orchestrator

A system for autonomous code development using multiple Claude agents that collaborate.

## Project Overview

This project enables multiple Claude "agents" (with different personas/roles) to work together autonomously:
- **Developer Agent**: Writes code based on tasks
- **Reviewer Agent**: Reviews code and provides feedback
- **Orchestrator**: Manages the loop until code is approved

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Run a task
python orchestrator.py --task "Your task here" --context-type ios

# Start API server
python server.py
```

## Key Files

| File | Purpose |
|------|---------|
| `orchestrator.py` | Main CLI tool - runs developer/reviewer loop |
| `server.py` | FastAPI server for HTTP access |
| `config/agents.yaml` | Agent personas and system prompts |
| `docs/cursor-integration.md` | How to use with Cursor IDE |

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
