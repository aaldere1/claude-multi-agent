# Claude Multi-Agent Orchestrator

Autonomous multi-agent system where Claude instances collaborate to develop, review, and refine code before any human intervention or commits.

## Primary Use Case: Cursor IDE Integration

The main workflow is **PR-aware code review** integrated with Cursor IDE:

```
You code in Cursor → Say "smart review" → External Claude agent reviews your changes
                                         → Checks PR context from GitHub
                                         → Verifies previous feedback addressed
                                         → Returns READY TO COMMIT or NEEDS WORK
```

### Quick Start for Cursor

1. Add the review script to your project (example: CineConcerts iOS app):
   ```bash
   cp scripts/review.sh /path/to/your/project/scripts/
   chmod +x /path/to/your/project/scripts/review.sh
   ```

2. Add a Cursor rule (`.cursor/rules/peer-review.mdc`) - see `examples/cursor-rule.mdc`

3. In Cursor chat, say: `smart review` or `local review`

4. Cursor runs the external reviewer and shows you the verdict.

---

## Concept

Instead of a single AI assistant, this system uses multiple Claude "agents" with different roles that communicate with each other:

```
┌─────────────────┐         ┌─────────────────┐
│ Developer Agent │ ◄─────► │ Reviewer Agent  │
│                 │         │                 │
│ • Writes code   │         │ • Reviews code  │
│ • Fixes issues  │         │ • Finds bugs    │
│ • Implements    │         │ • Suggests      │
│   features      │         │   improvements  │
└─────────────────┘         └─────────────────┘
         │                           │
         └───────────┬───────────────┘
                     ▼
          ┌─────────────────────┐
          │    Orchestrator     │
          │                     │
          │ • Manages loop      │
          │ • Tracks iterations │
          │ • Decides when done │
          └─────────────────────┘
```

## Architecture Options

### Option 1: Local Only (Recommended Start)

Everything runs on your Mac. Simplest setup.

```
Your Mac
├── Cursor/VS Code
│   └── Custom command triggers orchestrator
├── Orchestrator (Python script)
│   ├── Developer Agent (Claude API call)
│   └── Reviewer Agent (Claude API call)
└── Your codebase
```

**Pros:** Simple, no network complexity, fast
**Cons:** Uses your machine's resources

### Option 2: Local + Background Service

A persistent local API server that Cursor can call.

```
Your Mac
├── Cursor/VS Code
│   └── HTTP call to localhost:8000
├── FastAPI Server (always running)
│   └── Orchestrator endpoints
└── Your codebase
```

**Pros:** Async operations, persistent state, can run long tasks
**Cons:** Need to keep server running

### Option 3: Distributed (Local + Cloud)

Offload review/analysis to a cloud server.

```
Your Mac                          DigitalOcean Droplet
├── Cursor/VS Code                ├── Reviewer Agent
│   └── Triggers local agent      ├── Architecture Agent
├── Developer Agent               └── Testing Agent
│   └── Sends code for review ────────►
│   ◄──────── Receives feedback
└── Your codebase
```

**Pros:** Parallel processing, offload compute
**Cons:** Network latency, more complex setup

## Quick Start (Local Only)

### Prerequisites

- Python 3.10+
- Anthropic API key
- Cursor or VS Code

### Installation

```bash
# Clone this repo
git clone https://github.com/aaldere1/claude-multi-agent.git
cd claude-multi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### Basic Usage

```bash
# Run a simple developer-reviewer loop
python orchestrator.py --task "Add a logout button to the Settings screen"

# With specific file context
python orchestrator.py --task "Fix the memory leak" --files src/MyClass.swift

# With max iterations
python orchestrator.py --task "Implement dark mode" --max-iterations 3
```

### Cursor Integration

1. Create a custom command in Cursor (`.cursor/commands/review-loop.md`):

```markdown
---
name: review-loop
description: Run autonomous developer-reviewer loop
---

Run the multi-agent review loop for this task:
{selection}

Execute: `python /path/to/claude-multi-agent/orchestrator.py --task "{selection}"`
```

2. Use in Cursor: Type `/review-loop` and describe your task

## How It Works

### The Loop

```
1. YOU: Describe task
          │
          ▼
2. DEVELOPER AGENT: Writes initial implementation
          │
          ▼
3. REVIEWER AGENT: Analyzes code, returns verdict
          │
          ├── APPROVED → Commit & Done
          │
          └── CHANGES_REQUESTED → Feedback
                    │
                    ▼
4. DEVELOPER AGENT: Addresses feedback, iterates
          │
          └── Back to step 3

5. After N iterations or approval → Present to human
```

### Agent Personas

**Developer Agent**
- System prompt optimized for writing clean, functional code
- Receives task + any previous feedback
- Outputs code changes with explanations

**Reviewer Agent**
- System prompt optimized for critical code review
- Receives code diff/changes
- Outputs: APPROVED or CHANGES_REQUESTED with specific feedback

**Optional: Architect Agent**
- Consulted for larger changes
- Provides high-level design guidance
- Helps with patterns and structure

**Optional: Testing Agent**
- Generates test cases
- Identifies edge cases
- Validates implementation completeness

## Configuration

### Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_MODEL=claude-sonnet-4-20250514
MAX_ITERATIONS=5
LOG_LEVEL=INFO
```

### Agent Configuration

Edit `config/agents.yaml`:

```yaml
developer:
  model: claude-sonnet-4-20250514
  temperature: 0.3
  system_prompt: |
    You are a senior software developer. Write clean, well-documented code.
    Follow best practices for the language/framework in use.

reviewer:
  model: claude-sonnet-4-20250514
  temperature: 0.2
  system_prompt: |
    You are a strict but constructive code reviewer.
    Look for: bugs, security issues, performance problems, code smells.
    Return APPROVED if code is production-ready.
    Return CHANGES_REQUESTED with specific, actionable feedback if not.
```

## iOS Development Use Case

For Swift/SwiftUI development with Xcode:

```bash
# Review a SwiftUI view
python orchestrator.py \
  --task "Add pull-to-refresh to the playlist view" \
  --files "MyApp/Views/PlaylistView.swift" \
  --context-type ios

# The orchestrator will:
# 1. Developer agent writes SwiftUI code
# 2. Reviewer agent checks for iOS best practices
# 3. Loop until approved
# 4. Output final code for you to paste into Xcode
```

### iOS-Specific Agents

```yaml
ios_reviewer:
  system_prompt: |
    You are an iOS code reviewer specializing in Swift and SwiftUI.
    Check for:
    - Memory management (retain cycles, weak references)
    - Main thread violations
    - SwiftUI state management (@State, @Binding, @ObservedObject)
    - Accessibility compliance
    - iOS Human Interface Guidelines
```

## Communication Patterns

### Pattern 1: File-Based (Simple)

Agents communicate through files:

```
workspace/
├── task.md           # Current task description
├── code_changes.diff # Developer's output
├── review.md         # Reviewer's feedback
└── conversation.log  # Full history
```

### Pattern 2: In-Memory (Faster)

Agents communicate through Python objects - all in one process.

### Pattern 3: API-Based (Distributed)

For cloud deployment:

```
POST /api/develop
  → Developer agent processes task
  → Returns code changes

POST /api/review
  → Reviewer agent analyzes changes
  → Returns verdict + feedback

POST /api/orchestrate
  → Runs full loop autonomously
  → Returns final result
```

## Extending to Cloud (Optional)

If you want to run agents on a DigitalOcean droplet:

### Droplet Setup

```bash
# On droplet
sudo apt update && sudo apt install -y python3-pip python3-venv
git clone https://github.com/aaldere1/claude-multi-agent.git
cd claude-multi-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run as API server
python server.py --host 0.0.0.0 --port 8080
```

### Local → Droplet Communication

```python
# On your Mac, call the droplet
import requests

response = requests.post(
    "http://your-droplet-ip:8080/api/review",
    json={"code": code_diff, "context": "ios"}
)
feedback = response.json()["feedback"]
```

## Review Tools

### pr_review.py - PR-Aware Smart Review (Recommended)

Reviews your uncommitted changes with full GitHub PR context:

```bash
# Activate venv first
source venv/bin/activate

# Review with PR context
python pr_review.py --repo /path/to/repo

# With context about what you did
python pr_review.py --repo /path/to/repo --context "Fixed the memory leak"
```

**What it does:**
1. Detects current branch
2. Fetches PR description, review comments, CI status from GitHub
3. Gets your uncommitted changes (git diff)
4. Reviews changes against all that context
5. Reports: READY TO COMMIT or NEEDS WORK

### smart_review.py - Git Diff Review

Reviews git diff without PR context (faster, simpler):

```bash
python smart_review.py --repo /path/to/repo
python smart_review.py --repo /path/to/repo --context "Added error handling"
python smart_review.py --repo /path/to/repo --files specific/file.swift
```

### review.py - Quick File/Clipboard Review

Review a single file or clipboard content:

```bash
python review.py --file path/to/file.swift
python review.py --clipboard
python review.py --file path/to/file.swift --context cc  # CineConcerts context
```

## Cursor IDE Integration

### Setting Up Your Project

1. **Create the review script** in your project:

   ```bash
   # /your-project/scripts/review.sh
   #!/bin/bash
   cd ~/claude-multi-agent
   source venv/bin/activate

   REPO="/path/to/your/project"

   if [ "$1" == "--simple" ]; then
       shift
       python smart_review.py --repo "$REPO" --context "$1"
   elif [ -n "$1" ]; then
       python pr_review.py --repo "$REPO" --context "$1"
   else
       python pr_review.py --repo "$REPO"
   fi
   ```

2. **Create Cursor rule** at `.cursor/rules/peer-review.mdc`:

   ```markdown
   ---
   description: LOCAL code review using external Claude reviewer agent
   alwaysApply: true
   ---

   When user says: /review, smart review, local review

   Run this command:
   ./scripts/review.sh

   Show the output and summarize the verdict.
   ```

3. **Use trigger words** in Cursor chat:
   - `smart review`
   - `local review`
   - `/review`

## Roadmap

- [x] Basic orchestrator with developer + reviewer
- [x] Cursor command integration
- [x] iOS-specific agent personas
- [x] File-based context loading
- [x] API server mode
- [x] PR-aware review with GitHub integration
- [x] Git diff-based review (smart_review.py)
- [x] Quick file/clipboard review (review.py)
- [ ] Droplet deployment scripts
- [ ] Web UI for monitoring loops
- [ ] Slack/Discord notifications

## Related

- [Claude API Documentation](https://docs.anthropic.com)
- [Cursor Custom Commands](https://cursor.sh/docs)
- [Anthropic Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python)
