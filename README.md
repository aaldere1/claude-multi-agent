# Claude Review Agent

An AI-powered code review tool that integrates with Cursor IDE. Get instant, context-aware code reviews before you commit.

## What It Does

```
You code in Cursor → Say "local review" → External Claude agent reviews your changes
                                         ↓
                              • Fetches PR context from GitHub
                              • Checks if previous feedback was addressed
                              • Reviews your uncommitted changes
                              • Returns READY TO COMMIT or NEEDS WORK

              or → Say "team review" → 4 specialized reviewers in parallel
                                         ↓
                              • iOS Architect (patterns, data flow, async)
                              • Apple Design & UX (HIG, accessibility)
                              • Bug Hunter (crashes, memory, threading)
                              • Production Readiness (edge cases, shipping)
                                         ↓
                              • Synthesized priority-ranked report
```

**Key Features:**
- 🔍 **PR-Aware Reviews** - Knows your PR description, previous comments, CI status
- 👥 **Team Reviews** - 4 specialized reviewers analyze code in parallel, then synthesize
- 🤖 **Cursor Integration** - Just say "local review", "ask the reviewer", or "team review"
- ⚙️ **Project-Specific** - Learns your codebase patterns from a simple config file
- 🔄 **Mid-Task Validation** - Ask questions while coding, not just at the end

---

## Quick Start

### 1. Install the Tool

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/claude-review-agent.git ~/claude-review-agent
cd ~/claude-review-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### 2. Set Environment Variable

Add to your `~/.zshrc` or `~/.bashrc`:
```bash
export CLAUDE_REVIEW_HOME=~/claude-review-agent
```

Then reload: `source ~/.zshrc`

### 3. Set Up Your Project

```bash
cd ~/your-project

# Copy the review script
mkdir -p scripts
cp ~/claude-review-agent/examples/review.sh scripts/
chmod +x scripts/review.sh

# Copy the Cursor rule
mkdir -p .cursor/rules
cp ~/claude-review-agent/examples/cursor-rule.mdc .cursor/rules/peer-review.mdc

# (Optional) Add project-specific config
cp ~/claude-review-agent/examples/claude-review.yaml .claude-review.yaml
# Edit .claude-review.yaml with your project's patterns
```

### 4. Use in Cursor

In Cursor chat, say:
- `"local review"` - Full PR-aware review before committing
- `"team review"` - Multi-perspective review (4 specialized reviewers)
- `"ask the reviewer: is this approach correct?"` - Get guidance mid-task

---

## Project Configuration

Create `.claude-review.yaml` in your project root to customize reviews:

```yaml
# Project name
name: "My iOS App"

# Language (swift, python, typescript, javascript, go, rust, etc.)
language: swift

# Your codebase patterns - the reviewer will be aware of these
patterns:
  - "Services are singletons with @MainActor isolation"
  - "Use ImageCacheManager for all image caching"
  - "Views follow MVVM architecture"
  - "Use .backgroundStyle() modifier for consistent styling"
```

If no config exists, the tool uses sensible defaults based on the language.

---

## Cursor Integration

The Cursor rule (`.cursor/rules/peer-review.mdc`) teaches Cursor how to use the reviewer.

**Trigger phrases:**

| Say this... | What happens |
|-------------|--------------|
| `"local review"` | Full PR-aware review |
| `"smart review"` | Full PR-aware review |
| `"check with the reviewer"` | Ask a question with your current changes |
| `"ask the reviewer: ..."` | Ask a specific question |
| `"validate with reviewer"` | Validate your approach |
| `"team review"` | Multi-perspective team review (4 reviewers) |
| `"multi-perspective review"` | Same as team review |
| `"check with the team"` | Same as team review |

**Example workflows:**

> You: "Fix the memory leak in ProfileView. Check with the reviewer if you're unsure about the approach. Run local review before committing."
>
> Cursor: Makes changes, asks reviewer about weak self usage, gets confirmation, finishes all changes, runs full review, gets READY TO COMMIT, offers to commit.

> You: "I just refactored the navigation stack. Run a team review before I commit."
>
> Cursor: Runs `./scripts/review.sh --team "Refactored navigation stack"`. Four specialized reviewers analyze the changes in parallel. Returns a synthesized report with priority-ranked issues from architecture, UX, bug, and shipping perspectives.

---

## Command Line Usage

You can also use the tools directly:

```bash
# Activate the environment
cd ~/claude-review-agent
source venv/bin/activate

# PR-aware review (recommended)
python pr_review.py --repo ~/your-project

# PR-aware review with context
python pr_review.py --repo ~/your-project --context "Fixed the retain cycle"

# Multi-perspective team review (4 parallel reviewers)
python team_review.py --repo ~/your-project

# Team review with context
python team_review.py --repo ~/your-project --context "Refactored navigation"

# Simple review (no PR context, faster)
python smart_review.py --repo ~/your-project

# Review a single file
python review.py --file ~/your-project/src/MyClass.swift

# Review clipboard content
python review.py --clipboard
```

---

## How It Works

### PR-Aware Review (`pr_review.py`)

1. Detects your current branch
2. Fetches from GitHub:
   - PR description
   - Review comments
   - CI/build status
3. Gets your uncommitted changes (`git diff`)
4. Sends everything to Claude with your project config
5. Returns verdict: **READY TO COMMIT** or **NEEDS WORK**

### Team Review (`team_review.py`)

Runs 4 specialized reviewers in parallel, each examining your changes from a different angle:

| Reviewer | Focus |
|----------|-------|
| **iOS Architect** | Swift patterns, MVVM/data flow, @Observable, navigation, async/await, actors |
| **Apple Design & UX** | HIG compliance, accessibility (VoiceOver, Dynamic Type), Liquid Glass, layouts |
| **Bug Hunter** | Retain cycles, force unwraps, race conditions, MainActor, memory leaks |
| **Production Readiness** | Error handling, edge cases, App Store requirements, performance, localization |

After all 4 complete, a synthesis agent combines their findings into a single priority-ranked report with an **APPROVED** or **CHANGES_REQUESTED** verdict.

**Customize perspectives** in `.claude-review.yaml`:
```yaml
team_perspectives:
  - name: "Security"
    focus: "Authentication, authorization, Keychain usage, data privacy"
  - name: "Performance"
    focus: "View rebuild efficiency, lazy loading, caching, memory profiling"
  - name: "Accessibility"
    focus: "VoiceOver, Dynamic Type, color contrast, motor accessibility"
```

If not specified, defaults to the 4 iOS-focused perspectives above.

### Simple Review (`smart_review.py`)

Same as PR-aware but skips the GitHub PR context. Faster for quick checks.

### File Review (`review.py`)

Reviews a single file or clipboard content. Good for reviewing code snippets.

---

## Setting Up on Another Computer

1. **Clone the tool:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-review-agent.git ~/claude-review-agent
   cd ~/claude-review-agent
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Add your API key to .env
   ```

2. **Set environment variable:**
   ```bash
   echo 'export CLAUDE_REVIEW_HOME=~/claude-review-agent' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **For each project:**
   ```bash
   cd ~/your-project
   cp ~/claude-review-agent/examples/review.sh scripts/
   chmod +x scripts/review.sh
   cp ~/claude-review-agent/examples/cursor-rule.mdc .cursor/rules/peer-review.mdc
   # Optionally add .claude-review.yaml
   ```

---

## Requirements

- Python 3.10+
- Anthropic API key
- GitHub CLI (`gh`) for PR-aware features
- Cursor IDE (for IDE integration)

---

## Files

| File | Purpose |
|------|---------|
| `pr_review.py` | PR-aware review with GitHub context |
| `team_review.py` | Multi-perspective team review (4 parallel reviewers) |
| `smart_review.py` | Git diff review without PR context |
| `review.py` | Single file/clipboard review |
| `config_loader.py` | Loads project-specific configuration |
| `examples/review.sh` | Template script for projects |
| `examples/cursor-rule.mdc` | Template Cursor rule |
| `examples/claude-review.yaml` | Template project config |

---

## License

MIT
