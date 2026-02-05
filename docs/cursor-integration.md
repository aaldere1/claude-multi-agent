# Cursor Integration Guide

This guide explains how to integrate the multi-agent orchestrator with Cursor IDE.

## Option 1: Custom Command (Simplest)

Cursor supports custom commands that can execute shell scripts.

### Setup

1. In your project, create `.cursor/commands/` directory:
   ```bash
   mkdir -p .cursor/commands
   ```

2. Create a command file `.cursor/commands/review-loop.md`:
   ```markdown
   ---
   name: review-loop
   description: Run autonomous developer-reviewer loop
   ---

   Execute the multi-agent review loop for this task.

   ```bash
   python /path/to/claude-multi-agent/orchestrator.py \
     --task "{{selection}}" \
     --context-type general
   ```
   ```

3. Create an iOS-specific version `.cursor/commands/ios-review.md`:
   ```markdown
   ---
   name: ios-review
   description: Run iOS-specific code review loop
   ---

   Execute iOS development review loop.

   ```bash
   python /path/to/claude-multi-agent/orchestrator.py \
     --task "{{selection}}" \
     --context-type ios \
     --files "{{filepath}}"
   ```
   ```

### Usage

1. Select text describing your task (or the code to review)
2. Open command palette: `Cmd+Shift+P`
3. Type `/review-loop` or `/ios-review`
4. The orchestrator runs and outputs to terminal

## Option 2: Local API Server

Run the orchestrator as a local service that Cursor can call.

### Setup

1. Start the server:
   ```bash
   cd /path/to/claude-multi-agent
   source venv/bin/activate
   python server.py
   ```

2. Create a Cursor command that calls the API:
   ```markdown
   ---
   name: api-review
   description: Review via local API
   ---

   ```bash
   curl -X POST http://localhost:8000/api/orchestrate/sync \
     -H "Content-Type: application/json" \
     -d '{"task": "{{selection}}", "context_type": "ios"}'
   ```
   ```

### Benefits

- Server stays running (faster subsequent calls)
- Can handle async tasks
- Easy to extend with webhooks

## Option 3: Keyboard Shortcut

Bind a keyboard shortcut to trigger the orchestrator.

### Setup

1. Create a shell script `~/bin/ai-review.sh`:
   ```bash
   #!/bin/bash
   cd /path/to/claude-multi-agent
   source venv/bin/activate
   python orchestrator.py --task "$1" --context-type ios --json
   ```

2. Make it executable:
   ```bash
   chmod +x ~/bin/ai-review.sh
   ```

3. In Cursor settings, bind a shortcut to run the script with selection

## Workflow Examples

### Example 1: New Feature

1. Write a comment describing what you want:
   ```swift
   // TODO: Add a refresh button that reloads playlist data
   ```

2. Select the comment
3. Run `/ios-review`
4. Orchestrator generates implementation
5. Copy result into your code

### Example 2: Code Review

1. Select a block of code you want reviewed
2. Run `/review-loop` with task: "Review this code for bugs and improvements"
3. Get detailed feedback

### Example 3: Bug Fix

1. Paste error message
2. Select it with context
3. Run `/ios-review` with task: "Fix this error: [error message]"
4. Get fix suggestion

## Tips

### Include File Context

For better results, reference the current file:

```bash
python orchestrator.py \
  --task "Add error handling to the API call" \
  --files "{{filepath}}" "{{workspace}}/Models/Error.swift"
```

### Adjust Iterations

For complex tasks, increase max iterations:

```bash
python orchestrator.py --task "..." --max-iterations 7
```

### Quiet Mode

For cleaner output:

```bash
python orchestrator.py --task "..." --quiet --json
```

## Troubleshooting

### Command Not Found

Make sure the virtual environment is activated:
```bash
source /path/to/claude-multi-agent/venv/bin/activate
```

### API Key Issues

Verify your `.env` file has the correct key:
```bash
cat /path/to/claude-multi-agent/.env | grep ANTHROPIC
```

### Slow Response

The orchestrator makes multiple API calls. For faster iteration:
- Use `claude-haiku-...` model for reviewer (faster, cheaper)
- Reduce `--max-iterations`
