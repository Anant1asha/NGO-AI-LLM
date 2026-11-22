# Configuration Reference

Hachi reads configuration from four layers, **lowest to highest precedence**:

1. Built-in defaults
2. `settings.toml` — global (`~/.config/hachi/settings.toml`), then project-local (`<project>/.hachi/settings.toml`)
3. Environment variables and a project `.env` file
4. CLI flags

Run `hachi doctor` to see the resolved paths. Use [`settings.example.toml`](../../settings.example.toml)
(repo root) as a fully-commented starting template — copy it; never commit the real file.

- **[Part 1 — `settings.toml`](#part-1--settingstoml)** — every file key, the authority model, and the safety checks.
- **[Part 2 — Environment variables & operations](#part-2--environment-variables--operations)** — every variable the code reads, Windows secret-setting, and the always-on daemon.

---

# Part 1 — `settings.toml`

## File locations

| Scope | Path |
|-------|------|
| Global (user) | `~/.config/hachi/settings.toml` (Linux/macOS) or `%APPDATA%\hachi\settings.toml` (Windows) |
| Project-local | `<project>/.hachi/settings.toml` |

Project-local settings override global settings, which override built-in defaults.
Environment variables and `.env` files override both; CLI flags override everything.

**Both paths are listed in `.gitignore`.**  Use `settings.example.toml` (repo root)
as a template — copy and rename it; never commit the real file.

---

## Authority model

`settings.toml` is a **read-only authority file** from the agent's perspective.

- The agent reads config via `load_effective_config()` at session boot.
- The agent may call `write_global_config()` indirectly (via the settings UI or
  `hachi config-set`) but only for non-sensitive keys; it does not have direct
  filesystem write access to the config directory through its tool registry.
- `PermissionGate` enforces the tier, paths, and command rules declared here
  *before* any OS operation runs — the agent cannot override this at runtime.

---

## World-writable permission check

On POSIX (Linux / macOS), the config loader calls `stat()` on `settings.toml` and
warns if the file mode has the world-write bit set (`mode & 0o002`).

```
SECURITY: settings file /home/user/.config/hachi/settings.toml is world-writable
(mode 0o646). An unprivileged process could tamper with agent configuration.
Fix with: chmod o-w "/home/user/.config/hachi/settings.toml"
```

Set `HACHI_CONFIG_STRICT=1` in the environment to make this a hard error (raises
`PermissionError` and aborts config load).

On Windows, ACL-based permissions are used and this check is skipped silently.

---

## Strict mode

Setting the environment variable `HACHI_CONFIG_STRICT=1` (or passing `strict=True` to
`load_effective_config()`) switches from warning-mode to abort-mode for:

- World-writable `settings.toml` (raises `PermissionError`).
- Malformed TOML in the primary settings file (re-raises `tomllib.TOMLDecodeError`).
- Unknown top-level keys (raises `ValueError` listing them).

Recommended for CI and production deployments.

---

## Unknown-key validation

The loader compares every top-level key in the parsed TOML against the fields declared
on `ResolvedConfig`.  Unknown keys are logged as a warning:

```
settings file /home/user/.config/hachi/settings.toml contains unknown top-level
key(s): foo, bar. These keys are ignored. Check for typos or consult settings.example.toml.
```

Under `HACHI_CONFIG_STRICT=1` this is a hard error.

---

## Key reference

The authoritative list of keys and their defaults is in `settings.example.toml` at the
repository root.  Below is a compact summary by section.

### [meta]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `config_version` | int | `1` | Schema version for forward-compat checks |
| `imported_from_legacy` | bool | `false` | Set by migration wizard; do not edit |

### [provider]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `kind` | str | `"anthropic"` | LLM backend selector |
| `model` | str | `"claude-haiku-4-5"` | Model id sent to the provider |
| `base_url` | str\|null | `null` | Base URL for OpenAI-compatible endpoints |
| `api_key_env` | str\|null | `null` | **[SENSITIVE]** Env var holding the API key |
| `api_key_ref` | str\|null | `null` | **[SENSITIVE]** Secret-store reference |
| `allowed_models` | list[str] | `[]` | Allowlist; empty = no restriction |
| `headers` | dict[str,str] | `{}` | **[SENSITIVE]** Extra HTTP headers |

### [providers.\<name\>]

Named additional providers for multi-model routing.  Same fields as `[provider]`.

### [agent]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `name` | str | `""` | Display name in TUI/web |
| `persona` | str | `""` | System-prompt persona prefix |
| `max_tokens` | int | `8192` | Max tokens per generated turn |
| `temperature` | float | `0.0` | Sampling temperature |

### [permissions]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `tier` | str | `"guided"` | PermissionGate enforcement level |

`tier` choices: `"sandbox"` (read-only), `"guided"` (workspace write + shell approval),
`"unrestricted"` (no confirmation prompts).

#### [permissions.ask_before]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `spend_over_threshold` | bool | `true` | Pause before task exceeds per-task cost cap |
| `network_egress` | bool | `true` | Pause before off-machine data send |
| `delete_files` | bool | `true` | Pause before file deletion |

### [limits]

All values default to `null` (no cap).

| Key | Type | Effect |
|-----|------|--------|
| `max_daily_cost_usd` | float\|null | Rolling calendar-day spend cap in USD |
| `max_session_cost_usd` | float\|null | Per-session cumulative spend cap in USD |
| `max_turn_cost_usd` | float\|null | Per-turn spend cap in USD |
| `max_session_tokens` | int\|null | Per-session token limit (input + output) |
| `max_turn_tokens` | int\|null | Per-turn token limit |

### [memory]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `enable_session_history` | bool | `true` | Persist transcripts in SQLite |
| `enable_semantic_memory` | bool | `true` | Index facts into ChromaDB |
| `backend` | str | `"chroma"` | Vector store: `"chroma"` \| `"in_memory"` \| `"fts5_only"` |
| `graph` | bool | `false` | FTS5 + Chroma RRF fusion (experimental) |

### [voice]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `stt_model` | str\|null | `null` | STT model name (e.g. `"whisper-1"`) |
| `stt_base_url` | str\|null | `null` | STT endpoint base URL |
| `stt_api_key_env` | str\|null | `null` | **[SENSITIVE]** STT API key env var |
| `stt_provider` | str | `"openai"` | STT provider (only `"openai"` supported) |
| `tts_model` | str\|null | `null` | TTS model name (e.g. `"tts-1"`) |
| `tts_base_url` | str\|null | `null` | TTS endpoint base URL |
| `tts_api_key_env` | str\|null | `null` | **[SENSITIVE]** TTS API key env var |
| `tts_voice` | str\|null | `null` | Default TTS voice (e.g. `"alloy"`) |
| `tts_provider` | str | `"openai"` | TTS provider: `"openai"` \| `"elevenlabs"` |
| `elevenlabs_api_key_env` | str\|null | `null` | **[SENSITIVE]** ElevenLabs API key env var |
| `elevenlabs_voice_id` | str\|null | `null` | ElevenLabs voice id |

### [search]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `provider` | str\|null | `null` | Search provider (`"tavily"` to enable web search) |
| `max_calls_per_turn` | int | `10` | Max search/extract calls per turn |
| `cache_ttl_seconds` | float | `300.0` | In-session cache TTL in seconds |
| `window_max_calls` | int | `60` | Sliding-window rate limit call count |
| `window_seconds` | float | `3600.0` | Sliding-window duration in seconds |

### [files]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `max_size_bytes` | int | `52428800` | Upload ceiling in bytes (50 MB) |
| `allowed_types` | list[str] | `[]` | MIME type allowlist; empty = all allowed |
| `storage_backend` | str | `"local"` | Storage backend (`"local"` is the only active impl) |
| `scan_hook` | str | `"noop"` | Virus-scan hook (`"clamav"` / `"cloudmersive"` are future seams) |
| `index_on_extract` | bool | `true` | Index extracted text into Chroma for RAG |

### [routing]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `default_model` | str | `"claude-haiku-4-5"` | Fallback model id |
| `auto` | bool | `false` | Derive smart-default routing from the model registry |
| `capabilities` | dict[str, list[str]] | `{}` | Ordered candidate model-id lists per capability |
| `model_overrides` | list | `[]` | Extra ModelDescriptor dicts (highest registry precedence) |

#### [routing.resilience]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `max_attempts` | int | `3` | Max retry attempts |
| `backoff_base_s` | float | `0.5` | Exponential-backoff base in seconds |
| `timeout_s` | float | `60.0` | Per-attempt timeout in seconds |
| `breaker_threshold` | int | `5` | Consecutive failures before circuit breaker opens |
| `breaker_cooldown_s` | float | `30.0` | Cooldown in seconds before breaker re-closes |

### [events]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `bus_funnel` | bool | `false` | Route events through the EventBus singleton |

### [jobs]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `durable_handlers` | bool | `false` | Use named handlers for background jobs |
| `worker_count` | int | `1` | Job-queue worker-thread count |

### [observability]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `enabled` | bool | `false` | Enable tracing on gateway boot |
| `exporter` | str | `"console"` | Trace exporter: `"console"` \| `"otlp"` \| `"langfuse"` |
| `endpoint` | str\|null | `null` | OTLP exporter endpoint URL |
| `metrics_enabled` | bool | `false` | Also initialise the metrics facade |
| `log_format` | str | `"text"` | Log format: `"text"` (default) \| `"json"` (correlated JSON logs) |

### [channels.telegram]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `allowlist` | list[str] | `[]` | **[SENSITIVE]** Telegram chat ids allowed to reach the agent |

### [capabilities.\<name\>]

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `enabled` | bool | `false` | Enable the integration |
| `configured` | bool | `false` | Set by the setup wizard when credentials are stored |
| `secret_ref` | str\|null | `null` | Secret-store key for the integration credential |

Built-in capabilities: `google`, `notion`, `slack`.

### [mcp_servers.\<name\>]

Each sub-table registers one MCP server.

| Key | Type | Effect |
|-----|------|--------|
| `command` | str | Shell command to launch the server |
| `args` | list[str] | Arguments passed to `command` |
| `env` | dict[str,str] | Extra environment variables |
| `timeout_s` | float | Connection timeout in seconds (default: 30) |
| `enabled` | bool | Set to `false` to disable without removing the entry |

---

## Quick-start example

```toml
[provider]
kind = "anthropic"
model = "claude-haiku-4-5"
api_key_env = "ANTHROPIC_API_KEY"

[permissions]
tier = "guided"

[limits]
max_daily_cost_usd = 5.0
```

See `settings.example.toml` in the repository root for a fully-commented template
covering every section.

---

# Part 2 — Environment variables & operations

## Setting secrets on Windows

On Windows, `.env` files are **not auto-loaded by the OS or PowerShell**.  Hachi's CLI
does parse a project-level `.env` in the current working directory (via
`_load_dotenv_into_environ` in `cli/main.py`), but that only applies when you run
`hachi` from inside the project folder.  For reliable credential access — especially
when running the gateway as a service — use one of the methods below.

### Option 1 — Session-only (current PowerShell window)

```powershell
# Set for this terminal session only (gone when the window closes)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:HACHI_GATEWAY_API_TOKEN = "your-token-here"
```

### Option 2 — Persist for your user account (recommended)

```powershell
# Write to the user's persistent environment (survives reboots; takes effect in new terminals)
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
[System.Environment]::SetEnvironmentVariable("HACHI_GATEWAY_API_TOKEN", "your-token-here", "User")
```

Or using the classic `setx` command (equivalent, but note `setx` does **not** update the
current session — open a new terminal after running it):

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
setx HACHI_GATEWAY_API_TOKEN "your-token-here"
```

### Option 3 — Keyring vault (most secure)

Run the interactive setup once; Hachi stores the key in the Windows Credential Manager so
it never has to live in plaintext in environment variables or files:

```powershell
hachi quickstart   # or: hachi setup --tier lightning
```

During setup, paste your API key when prompted.  Hachi calls
`keyring.set_password("hachi", "ANTHROPIC_API_KEY", <key>)` under the hood, which stores
it in Windows Credential Manager.  On subsequent runs the key is loaded from the vault
automatically — no env var needed.

To inspect or manage stored secrets:

```powershell
hachi secrets --list    # show what is stored in the vault
hachi secrets --check   # probe that the keyring backend is healthy
```

### Option 4 — Project `.env` file

Place a `.env` file in the directory you run `hachi` from:

```
ANTHROPIC_API_KEY=sk-ant-...
HACHI_GATEWAY_API_TOKEN=your-token-here
```

Hachi merges this into `os.environ` on startup (existing env vars are **not** overwritten,
so Option 1/2/3 take precedence).  This is the closest Windows equivalent of the
`export VAR=...` pattern used in Unix shell profiles.

> **Note:** If you run the gateway as a Windows Task Scheduler service
> (`hachi daemon install`), neither the current session nor `.env` will apply — use
> Option 2 (persistent user env var) or the keyring vault so the service process
> inherits the credentials.

## Provider & model

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | – | API key for the `anthropic` provider. |
| `OPENAI_API_KEY` | – | API key for the `openai-compatible` provider. |
| `OPENROUTER_API_KEY` | – | API key for the `openrouter` provider (200+ models). |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL for `openai-compatible`. |
| `OLLAMA_HOST` | `http://127.0.0.1:11434/v1` | Endpoint for the local `ollama` provider. |
| `GEMINI_API_KEY` | – | Free API key for the `gemini` provider (get one at https://aistudio.google.com/). |
| `GOOGLE_AI_API_KEY` | – | Alias for `GEMINI_API_KEY` (checked if the primary is unset). |
| `CHATGPT_SESSION_TOKEN` | – | Browser session cookie for the `chatgpt-web` unofficial provider. |
| `CHATGPT_ACCESS_TOKEN` | – | Pre-resolved JWT access token for `chatgpt-web` (alternative to session cookie). |
| `HACHI_MODEL` | `claude-haiku-4-5` | Override the configured model id. |
| `HACHI_MAX_TOKENS` | `8192` | Max output tokens per LLM call. |

Supported provider kinds: `anthropic`, `openai-compatible`, `openrouter`, `groq`, `together`, `deepseek`, `ollama`, `gemini`, `chatgpt-web`.

### Model selection & guardrail (`settings.toml`)

```toml
[provider]
kind = "anthropic"
model = "claude-haiku-4-5"
# Hard guardrail: when set, ONLY these models may be selected via /model.
# Leave empty (or omit) to allow any model the provider exposes.
allowed_models = ["claude-haiku-4-5", "claude-sonnet-4-5"]
```

In the TUI, `/model` lists the models the provider currently exposes (discovered
live via the provider's models API, falling back to a curated list when offline).
If `allowed_models` is set, the list — and what `/model <name>` will switch to —
is restricted to exactly those entries.

### Voice input (speech-to-text)

The `transcribe_audio` tool transcribes a local audio file via an OpenAI-compatible
`/audio/transcriptions` endpoint. Credentials resolve lazily; the tool degrades to a
"not configured" hint until set.

| Variable | Default | Purpose |
|----------|---------|---------|
| `HACHI_STT_API_KEY` | `OPENAI_API_KEY` | API key for transcription (falls back to the OpenAI key). |
| `HACHI_STT_BASE_URL` | `OPENAI_BASE_URL` or `https://api.openai.com/v1` | Whisper-compatible endpoint (e.g. Groq, a local server). |
| `HACHI_STT_MODEL` | `whisper-1` | Transcription model id. |

### Voice output (text-to-speech)

The `speak_text` tool synthesizes speech to a local audio file via an OpenAI-compatible
`/audio/speech` endpoint. Same lazy-cred + graceful-degradation pattern.

| Variable | Default | Purpose |
|----------|---------|---------|
| `HACHI_TTS_API_KEY` | `OPENAI_API_KEY` | API key for synthesis (falls back to the OpenAI key). |
| `HACHI_TTS_BASE_URL` | `OPENAI_BASE_URL` or `https://api.openai.com/v1` | Speech-compatible endpoint. |
| `HACHI_TTS_MODEL` | `tts-1` | Synthesis model id. |
| `HACHI_TTS_VOICE` | `alloy` | Default voice (provider-specific). |

## Safety, budgets & rate limits

| Variable | Default | Purpose |
|----------|---------|---------|
| `HACHI_PERMISSION_TIER` | – | Override the permission tier (`sandbox`/`guided`/`unrestricted`). |
| `HACHI_MAX_SESSION_COST_USD` | `0` (off) | Stop a session once estimated spend reaches this (USD). |
| `HACHI_MAX_SESSION_TOKENS` | `0` (off) | Stop a session once total tokens reach this. |
| `HACHI_CHANNEL_RATE_LIMIT` | `30` | Max channel-webhook messages per sender per minute. |
| `HACHI_OPENAI_RATE_LIMIT` | `60` | Max `/v1/chat/completions` requests per minute. |
| `HACHI_CHANNEL_ALLOWLIST` | – | Comma list of `sender` or `channel:sender` allowed to use the webhook. |

Budget caps can also be set in `settings.toml`:

```toml
[limits]
max_session_cost_usd = 1.50
max_session_tokens = 500000
```

## Gateway (`hachi gateway`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `HACHI_GATEWAY_API_TOKEN` | – | Bearer token required for protected gateway routes. |
| `HACHI_GATEWAY_API_TOKEN_FILE` | – | Read the token from a file (Docker-secret friendly). |
| `HACHI_GATEWAY_MAX_SESSIONS` | `100` | Max concurrent sessions. |
| `HACHI_GATEWAY_MAX_PROMPT_CHARS` | `100000` | Max characters per prompt. |
| `HACHI_CORS_ORIGINS` | `localhost:5173,4173` | Comma list of allowed CORS origins (`*` for any). |

## Channels & outbound calls

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | – | Bot token for `hachi channel telegram` (inbound) **and** the `send_telegram_message` tool (outbound). |
| `TELEGRAM_CHAT_ID` | – | Default chat id for `send_telegram_message` (user, group, or channel). Required unless passed per-call. |
| `META_WHATSAPP_TOKEN` | – | Meta WhatsApp Business bearer token (`hachi channel whatsapp` inbound + `send_whatsapp_message` outbound). |
| `META_WHATSAPP_PHONE_ID` | – | Meta sender phone-number ID (from the Meta App Dashboard). |
| `META_WHATSAPP_VERIFY_TOKEN` | – | Webhook verify token to match in the Meta App Dashboard. Used by `hachi channel whatsapp` for the GET verification handshake. |
| `TWILIO_ACCOUNT_SID` | – | Twilio Account SID (alternative to Meta Cloud API for WhatsApp). |
| `TWILIO_AUTH_TOKEN` | – | Twilio Auth Token. |
| `TWILIO_WHATSAPP_FROM` | – | Twilio WhatsApp sender (e.g. `whatsapp:+14155238886`). |
| `SLACK_BOT_TOKEN` | – | Slack bot token for `send_slack_message` (`chat.postMessage`; pass a channel). |
| `SLACK_WEBHOOK_URL` | – | Slack incoming-webhook URL (single channel; alternative to a bot token). |
| `DISCORD_WEBHOOK_URL` | – | Discord webhook URL for `send_discord_message` (single channel). |
| `DISCORD_BOT_TOKEN` | – | Discord bot token (alternative to a webhook; pass a channel id). |
| `HACHI_SMTP_HOST` | `smtp.gmail.com` | SMTP server for `send_email_digest` and notification digests. |
| `HACHI_SMTP_PORT` | `587` | SMTP port (STARTTLS). |
| `HACHI_SMTP_USER` | – | SMTP username / sender address. Required to enable email notifications. |
| `HACHI_SMTP_PASSWORD` | – | SMTP password or app-specific password. |
| `HACHI_SMTP_FROM` | `SMTP_USER` | Override the From: address (defaults to `SMTP_USER`). |
| `HACHI_SMTP_TO` | – | Default recipient for `send_email_digest` and digest flushes. |
| `HACHI_REST_ALLOWLIST` | – | Comma list of hosts the Universal REST Adapter may call. |
| `HACHI_REST_ALLOW_PRIVATE` | `false` | Allow REST/webhook **and browser** calls to private/loopback hosts (use with care). |
| `HACHI_ALLOW_OUTBOUND_SECRETS` | `false` | When `true`, disables automatic redaction of API keys/tokens/private keys in outbound Slack/Discord/WhatsApp/Telegram messages. Leave off so secrets can't be accidentally leaked. |

## Optional features (extras)

Some capabilities ship as optional dependency groups so the base install stays lean:

| Extra | Install | Enables |
|-------|---------|---------|
| `browser` | `pip install 'hachi-og[browser]'` then `playwright install chromium` | Headless browser tools (`browse_web`, `browser_act`, `browser_screenshot`). Disabled in the `sandbox` permission tier; URLs are validated like other outbound calls. |
| `tracing` | `pip install 'hachi-og[tracing]'` | OpenTelemetry tracing. Enable at runtime with `HACHI_TRACING=true` (console exporter); emits spans for LLM and tool calls. No-op when the extra is absent or the flag is unset. |

Google/Notion/Slack integrations need no extra install — they authenticate over
`httpx` (a base dependency) via OAuth (Google) or pasted API tokens (Notion, Slack).

## Integrations & secrets

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | – | OAuth client for Google Workspace integration. |
| `HACHI_SECRET_PASSPHRASE` | – | Passphrase for the encrypted secret-store fallback (when no OS keyring). |

## Install script overrides

| Variable | Default | Purpose |
|----------|---------|---------|
| `HACHI_REPO` | the public repo | Source repo for `install.sh` / `install.ps1`. |
| `HACHI_HOME` | `~/.hachi-src` | Where the installer clones Hachi. |

## Always-on background daemon

Hachi can run the gateway as a persistent background service that starts
automatically when you log in.  This powers proactive scheduling — the
`schedule run-due` tick happens continuously without a manual `hachi schedule run-due` call.

### Install / manage

```bash
# Install the daemon (auto-starts the gateway on every login)
hachi daemon install

# Custom bind address / port
hachi daemon install --host 0.0.0.0 --port 8888

# Check if the daemon is running
hachi daemon status

# Start / stop without re-installing
hachi daemon start
hachi daemon stop

# Remove the daemon completely
hachi daemon uninstall
```

### Platform details

| Platform | Mechanism | Service file |
|----------|-----------|-------------|
| macOS | launchd user agent (`launchctl load -w`) | `~/Library/LaunchAgents/ai.hachi.gateway.plist` |
| Linux | systemd user service (`systemctl --user enable --now`) | `~/.config/systemd/user/hachi.service` |
| Windows | Task Scheduler (`schtasks /sc ONLOGON`) | Task name: `Hachi Gateway` |

The daemon writes stdout/stderr to `{state_dir}/gateway.log`
(run `hachi doctor --json | jq .state_dir` to find the path).

### Schedule runner

Once the daemon is running, scheduled tasks fire automatically.
You can still run due schedules manually:

```bash
hachi schedule run-due
```

For a lightweight cron-only setup (no full gateway), call `run-due` from the
system cron instead of installing the daemon:

```
# crontab -e
*/5 * * * * hachi schedule run-due >> ~/.hachi-schedule.log 2>&1
```
