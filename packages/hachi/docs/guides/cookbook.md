# Hachi Cookbook

Practical, copy-paste recipes for the most common tasks.
Each recipe shows the exact commands to run and what you will see.

---

## Table of Contents

1. [First-time setup](#1-first-time-setup)
2. [Chat with the agent (TUI)](#2-chat-with-the-agent-tui)
3. [Run a one-shot task from the CLI](#3-run-a-one-shot-task-from-the-cli)
4. [Switch model providers](#4-switch-model-providers)
5. [Google Workspace integration](#5-google-workspace-integration)
6. [Generate a PowerPoint presentation](#6-generate-a-powerpoint-presentation)
7. [Import conversation history](#7-import-conversation-history)
8. [Work with sessions](#8-work-with-sessions)
9. [Write and load a custom skill (.og)](#9-write-and-load-a-custom-skill-og)
10. [Delegate to a sub-agent](#10-delegate-to-a-sub-agent)
11. [Schedule recurring tasks](#11-schedule-recurring-tasks)
11b. [Run the agent as an always-on background daemon](#11b-run-the-agent-as-an-always-on-background-daemon)
12. [Voice — transcribe and speak](#12-voice--transcribe-and-speak)
13. [Permissions & security tiers](#13-permissions--security-tiers)
14. [Diagnose problems](#14-diagnose-problems)

---

## 1. First-time setup

```bash
# Install with uv (Python 3.11+ required)
pip install uv          # or brew install uv / scoop install uv
uv tool install hachi-og

# Run the interactive setup wizard
hachi setup --tier lightning
```

The wizard asks for your API key (Anthropic by default), writes
`~/.config/hachi/settings.toml`, and verifies the connection.

**Skip the wizard** — set env vars instead:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
hachi run          # starts immediately
```

---

## 2. Chat with the agent (TUI)

```bash
hachi run
```

The Textual TUI opens. Type your message and press **Enter**.

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Quit |
| `Ctrl+L` | Clear screen |
| `/help`  | List slash commands |
| `/tools` | Show loaded tool groups |
| `/skills`| List available .og skills |

**Resume a previous session:**

```bash
# Interactively pick a past session to resume (numbered list):
hachi run --resume

# Or jump straight back into the most recent session:
hachi run --continue

# List sessions first if you want to see what's there:
hachi session list
```

---

## 3. Run a one-shot task from the CLI

```bash
# Pipe a prompt in
echo "Summarise CHANGELOG.md in three bullet points" | hachi run --once

# Or pass it directly
hachi run --once "What files changed in the last git commit?"
```

`--once` runs a single turn, prints the response, and exits — no TUI.
Useful in shell scripts and CI.

---

## 4. Switch model providers

Edit `~/.config/hachi/settings.toml`:

```toml
[provider]
kind  = "anthropic"
model = "claude-opus-4-8"
```

**OpenAI:**

```toml
[provider]
kind  = "openai-compatible"
model = "gpt-4o"
# set OPENAI_API_KEY in your environment
```

**Local Ollama:**

```bash
ollama pull llama3
```

```toml
[provider]
kind  = "ollama"
model = "llama3"
# OLLAMA_HOST defaults to http://127.0.0.1:11434/v1
```

**OpenRouter (200+ models, one key):**

```toml
[provider]
kind  = "openrouter"
model = "anthropic/claude-opus-4"
# set OPENROUTER_API_KEY in your environment
```

Restart the agent after changing the config.

---

## 5. Google Workspace integration

### Prerequisites

No extra install needed — the Google integration authenticates via OAuth over
`httpx`, which is a base dependency.

Enable Google OAuth in settings:

```toml
[integrations.google]
enabled = true
client_id     = "YOUR_OAUTH_CLIENT_ID"
client_secret = "YOUR_OAUTH_CLIENT_SECRET"
```

First `hachi run` triggers a browser OAuth consent screen. Credentials
are stored in the system keychain — you only authenticate once.

### Example prompts

```
> Check my calendar for tomorrow
> Create a weekly standup every Monday at 10am IST with a Meet link
> What are my pending Google Tasks?
> Plan my day for 2026-06-10 — include calendar, email, and tasks
> Draft an email to ops@example.com and schedule it for 9am
```

### Available tools (loaded automatically)

| Tool | What it does |
|------|-------------|
| `google_list_events` | Next N calendar events |
| `google_create_event` | One-off event |
| `google_create_recurring_event` | RRULE-based recurring event |
| `google_get_events_for_date` | All events on a specific date |
| `google_list_tasks` / `google_create_task` | Google Tasks CRUD |
| `google_complete_task` | Mark a task done |
| `google_plan_my_day` | Synthesise calendar + Gmail + Tasks into a day plan |
| `google_list_emails` | Recent inbox |
| `google_search_emails` | Gmail search |
| `google_send_email` | Send email |
| `google_create_doc` | New Google Doc |
| `google_search_drive` | Search Google Drive |

---

## 6. Generate a PowerPoint presentation

The agent can build `.pptx` files directly — no PowerPoint required.

### Install the optional dependency

```bash
uv tool install "hachi-og[presentations]"
# or inside the dev repo:
uv sync --extra presentations
```

### Example prompts

```
> Create a 5-slide pitch deck about our Q3 roadmap.
  Themes: market opportunity, product vision, key milestones, team, ask.
  Use the professional theme and save to ~/Desktop/Q3_Pitch.pptx

> Build a dark-themed onboarding presentation with slides:
  Welcome | What is Hachi | First steps | Getting help
  Include presenter notes on each slide.
```

### Direct tool call (for scripting)

```python
# Using the Hachi Python SDK (coming soon) or via agent tool call:
{
  "tool": "generate_presentation",
  "title": "Q3 Roadmap",
  "subtitle": "June 2026",
  "theme": "professional",
  "output_path": "~/Desktop/Q3_Roadmap.pptx",
  "slides": [
    {
      "heading": "Market Opportunity",
      "bullets": ["$4B TAM", "35% YoY growth", "Underserved SMB segment"],
      "notes": "Reference the Gartner report here."
    },
    {
      "heading": "Product Vision",
      "bullets": ["Autonomous agent engine", "No-code skill authoring", "Native Google integration"]
    }
  ]
}
```

**Available themes:** `default` · `dark` · `light` · `professional`

Output defaults to `~/Downloads/<title>.pptx` when no path is given.

---

## 7. Import conversation history

Bring your ChatGPT, Gemini, or Hermes history into Hachi so the agent
remembers your past conversations.

### Export from each platform

| Platform | How to export |
|----------|---------------|
| **ChatGPT** | Settings → Data Controls → Export data → download `conversations.json` |
| **Gemini** | Google Takeout → select "Gemini Apps Activity" → download `conversations.json` |
| **Hermes** | Session export in the Hermes UI → `sessions.json` |

### Import

```bash
# Auto-detect format
hachi memory import ~/Downloads/conversations.json

# Explicit format
hachi memory import ~/Downloads/conversations.json --format chatgpt

# Dry run — shows what would be imported without writing anything
hachi memory import ~/Downloads/conversations.json --dry-run

# Import history only (skip MemoryVault semantic indexing)
hachi memory import ~/Downloads/conversations.json --no-memory

# JSON output for scripting
hachi memory import ~/Downloads/conversations.json --json
```

Each conversation becomes a searchable session and a MemoryVault fact.
After import, `hachi session list` shows the imported conversations
with their original titles.

---

## 8. Work with sessions

```bash
# List recent sessions (most recent first)
hachi session list

# Show a session transcript
hachi session show <session-id>

# Search across all sessions
hachi session search "OAuth bug"

# Export a session to JSON
hachi session export <session-id> > session.json

# Delete a session
hachi session delete <session-id>

# Backfill titles for sessions that have none
hachi session retitle

# Force-regenerate titles for all sessions
hachi session retitle --force
```

---

## 9. Write and load a custom skill (.og)

Skills are `.og` files that teach the agent a specialised capability.
The agent reads them in 3 passes (index → summary → full) to minimise
token usage.

**Minimal skill template** (`my-skill.og`):

```
::index
name: my-skill
description: Brief description for routing (shown in list_skills)
tags: [custom, example]
::

::dense
What this skill does and when the agent should reach for it.
::

::full
## Detailed instructions

Step-by-step guidance, tool names, example inputs/outputs.
Place long reference content here — it is only loaded on demand.
::
```

**Install the skill:**

```bash
# Copy to the skills directory
cp my-skill.og "$(hachi doctor --json | jq -r '.skills_dir')/my-skill.og"

# Or ask the agent to save it inline:
# > Save the following as a skill called my-skill: ...
```

**Load the skill in a session:**

```
> load skill my-skill
> [now the agent has access to everything in ::full]
```

---

## 10. Delegate to a sub-agent

Sub-agents run in isolation with their own tool registry and a specialised
brain loaded from a matching `brain-<role>.og` skill.

```
> Delegate to the researcher role:
  summarise the top 5 Python async frameworks released in 2025

> Delegate to the coder role:
  write a FastAPI endpoint that proxies requests to api.example.com/data
  and caches responses for 60 seconds
```

Results come back to the main session via `delegation_log`.
The main context stays clean — the sub-agent's tool calls don't pollute
your history.

**Available built-in roles** (add more by creating `brain-<role>.og` skills):

- `researcher` — web search + summarisation
- `coder` — write and test code
- `analyst` — data analysis and charting

---

## 11. Schedule recurring tasks

```
> Every weekday at 8am, check my Google Tasks and send me a morning briefing
> Set a reminder every Friday at 4pm: prepare the weekly team update
> Run the test suite every hour and notify me if it fails
```

Schedules are persisted in `~/.local/share/hachi/schedules.db` and
survive restarts.

**CLI management:**

```bash
hachi schedule list
hachi schedule remove <schedule-id>
```

---

## 11b. Run the agent as an always-on background daemon

By default, scheduled tasks only fire when you manually run
`hachi schedule run-due`. Install the daemon so they fire automatically
24/7, even when no terminal is open.

```bash
# Install the gateway as a background service (auto-starts on login)
hachi daemon install

# Check the daemon is running
hachi daemon status

# Temporarily stop it (does NOT uninstall)
hachi daemon stop
hachi daemon start

# Remove completely
hachi daemon uninstall
```

The daemon binds to `127.0.0.1:8787` by default. Use `--host`/`--port` to
change:

```bash
hachi daemon install --host 0.0.0.0 --port 8888
```

Logs go to `{state_dir}/gateway.log` — find the path with
`hachi doctor --json | jq -r '.state_dir'`.

**Platform:** macOS (launchd) · Linux (systemd --user) · Windows (Task Scheduler).

---

## 11c. Chat with Hachi on WhatsApp

Hachi can receive and reply to WhatsApp messages via a local webhook server
compatible with both the **Meta Cloud API** and **Twilio**.

### Quick start (Meta Cloud API)

```bash
# 1. Set credentials (Meta App Dashboard → WhatsApp → API Setup)
export META_WHATSAPP_TOKEN=<bearer-token>
export META_WHATSAPP_PHONE_ID=<phone-number-id>
export META_WHATSAPP_VERIFY_TOKEN=mysecret   # any string you choose

# 2. Start the webhook server
hachi channel whatsapp --port 8080 --verify-token "$META_WHATSAPP_VERIFY_TOKEN"

# 3. Expose it publicly (ngrok, Cloudflare Tunnel, etc.)
ngrok http 8080
# → copy the HTTPS URL into Meta App Dashboard → Webhooks → Edit → Callback URL
```

### Quick start (Twilio)

```bash
export TWILIO_ACCOUNT_SID=ACxxx
export TWILIO_AUTH_TOKEN=<auth-token>
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

hachi channel whatsapp --port 8080
# Point Twilio Sandbox → "When a message comes in" to https://<your-host>/
```

### Restrict access

```bash
# Only allow messages from these E.164 numbers
hachi channel whatsapp --allow "+447911123456,+14155238886"
```

---

## 12. Voice — transcribe and speak

### Transcribe audio

```
> Transcribe the voice note at ~/voice-notes/meeting-2026-06-07.m4a
> Transcribe and summarise ~/recordings/standup.wav in 3 bullet points
```

Supported formats: `mp3`, `m4a`, `wav`, `webm`, `flac`, `ogg`.
Requires an OpenAI-compatible API key with Whisper access:

```toml
[voice]
stt_provider = "openai"
# set OPENAI_API_KEY in your environment
```

### Text to speech

```
> Read aloud: "Your standup is in 5 minutes."
> Generate a voice file for the following and save to ~/welcome.mp3: Welcome to Hachi!
```

```toml
[voice]
tts_provider = "openai"
tts_voice    = "nova"   # alloy | echo | fable | onyx | nova | shimmer
```

---

## 13. Permissions & security tiers

Hachi ships three tiers that gate what the agent can do:

| Tier | What's allowed |
|------|---------------|
| `sandbox` | Read files only; no shell, no network, no writes |
| `standard` | Read + write within `allowed_paths`; shell commands from allowlist |
| `lightning` | Full access — trusted environment (dev box, local only) |

**Set the tier** in `settings.toml`:

```toml
[permissions]
tier = "standard"
allowed_paths = ["~/projects", "~/Downloads"]
```

**Audit what the agent can access:**

```bash
hachi security-audit
hachi security-audit --json          # machine-readable output
hachi security-audit --fail-on-high  # exit 1 if any HIGH findings
```

---

## 14. Diagnose problems

```bash
# Full diagnostics — checks API keys, paths, DB, permissions
hachi doctor

# JSON output for scripting
hachi doctor --json
```

**Common issues:**

| Symptom | Fix |
|---------|-----|
| `ANTHROPIC_API_KEY not set` | Export the key or run `hachi setup` |
| `ChromaDB unavailable` | `uv sync --extra memory` |
| `python-pptx not found` | `uv sync --extra presentations` |
| `Google OAuth failed` | Check `client_id`/`client_secret` in settings.toml |
| TUI won't start on Windows | Ensure Windows Terminal or a VT100-capable console |
| Tests fail with `OSError: [Errno 4551]` | Use `uv run python -m pytest` (not bare `pytest`) |

---

## Getting help

- Run `hachi --help` or `hachi <command> --help` for CLI docs.
- In the TUI, type `/help` for a list of slash commands.
- Open an issue: https://github.com/OpenGigantic/hachi/issues
