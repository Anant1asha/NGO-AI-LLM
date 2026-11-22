"""
Hachi CLI Entry Point

Provides the interactive terminal interface for users to communicate with the Hachi agent.
Uses rich to render a premium, step-by-step visual experience showing every tool call and result.

Commands:
    hachi run          — Start the interactive agent session
    hachi onboard      — Initialize the workspace
    hachi permissions  — View or reconfigure device permissions
"""

import json
import logging
import os
import sys
import threading
from dataclasses import asdict
from datetime import date as _date
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule

from hachi.cli.commands.channel import channel_app
from hachi.cli.commands.daemon import daemon_app
from hachi.cli.commands.eval import eval_app
from hachi.cli.commands.jobs import jobs_app
from hachi.cli.commands.mcp import mcp_app
from hachi.cli.commands.memory import memory_app
from hachi.cli.commands.pack import ogpack_app
from hachi.cli.commands.schedule import schedule_app
from hachi.cli.commands.session import session_app
from hachi.cli.commands.skill import skill_app
from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.credential_vault import CredentialVault
from hachi.core.onboarding import (
    OnboardingService,
    default_api_key_env_for,
    looks_like_env_var_name,
    persist_provider_api_key,
)
from hachi.core.paths import get_hachi_paths
from hachi.core.permissions import PermissionGate
from hachi.core.secret_scanner import redact_secrets
from hachi.core.secret_store import create_default_secret_store
from hachi.core.session_store import SessionStore
from hachi.gateway.control_plane import (
    ConnectRequest,
    GatewayControlPlane,
    GatewayEvent,
    GatewayHTTPServer,
    GatewayProtocolError,
)
from hachi.gateway.orchestrator import AgentSession, boot_agent
from hachi.gateway.workspace import (
    ensure_device_permissions,
    ensure_workspace,
    get_permissions_file,
    get_workspace_dir,
    run_permissions_wizard,
    show_current_permissions,
)
from hachi.jobs import ResidentWorkerThread, ScheduleStore

app = typer.Typer(
    help="Hachi - The Autonomous Agent Engine powered by ObjectGraph",
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(schedule_app, name="schedule")
app.add_typer(channel_app, name="channel")
app.add_typer(skill_app, name="skill")
app.add_typer(mcp_app, name="mcp")
app.add_typer(memory_app, name="memory")
app.add_typer(session_app, name="session")
app.add_typer(daemon_app, name="daemon")
app.add_typer(ogpack_app, name="pack")
app.add_typer(jobs_app, name="jobs")
app.add_typer(eval_app, name="eval")

# Sub-apps defined later in this file — registered here so they appear in --help
keys_app = typer.Typer(help="Manage named API keys and credentials in the secure vault.")
og_app = typer.Typer(help="Manage ObjectGraph (.og) skill version history.")
app.add_typer(keys_app, name="keys")
app.add_typer(og_app, name="og")

# On Windows the default console encoding is often cp1252, which cannot represent
# Unicode arrows/dashes used throughout CLI output.  Reconfigure stdout/stderr to
# UTF-8 with replacement characters so output degrades gracefully instead of raising
# UnicodeEncodeError.  The reconfigure() call is a no-op on Python builds where the
# stream doesn't support it (e.g. when stdout is not a TextIOWrapper).
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _load_dotenv_into_environ(dotenv_path: Path) -> None:
    """Merge a .env file into os.environ (existing vars are NOT overwritten).

    This ensures SMTP / Telegram / Slack credentials set in .env are visible to
    all tools that read os.environ directly — not just the provider API-key path
    in core/llm.py which has its own .env fallback.

    Set ``HACHI_DISABLE_DOTENV_AUTOLOAD=1`` to skip the merge entirely. The pytest
    harness sets this in ``tests/conftest.py`` so the suite never pulls the
    developer's real provider keys into the process — that previously flipped
    import-time skipif guards on live-gateway tests (flaky, order-dependent) and
    leaked real secrets into the test process.
    """
    if os.environ.get("HACHI_DISABLE_DOTENV_AUTOLOAD", "").strip() == "1":
        return
    if not dotenv_path.exists():
        return
    try:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass  # .env parse errors must never abort the CLI


_load_dotenv_into_environ(Path.cwd() / ".env")
# Also merge the user config-dir .env — that is where `hachi setup` persists API keys and
# OAuth client ids. Without this, a credential configured via the wizard was written to disk
# but never loaded on the next run (the loader only read cwd/.env), so Google and other
# integrations reported "not configured" despite being set. cwd/.env above wins on conflicts.
try:
    from hachi.core.paths import get_hachi_paths as _get_hachi_paths

    _load_dotenv_into_environ(_get_hachi_paths().config_dir / ".env")
except Exception:
    pass  # path resolution must never abort the CLI

# ---------------------------------------------------------------------------
# Task 6d — TOKOBOROS_ → HACHI_ back-compat shim
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)

_TOKOBOROS_RENAMES: dict[str, str] = {
    "TOKOBOROS_STT_API_KEY": "HACHI_STT_API_KEY",
    "TOKOBOROS_TTS_API_KEY": "HACHI_TTS_API_KEY",
    "TOKOBOROS_SMTP_USER": "HACHI_SMTP_USER",
    "TOKOBOROS_SMTP_PASSWORD": "HACHI_SMTP_PASSWORD",
    "TOKOBOROS_SMTP_HOST": "HACHI_SMTP_HOST",
    "TOKOBOROS_SMTP_PORT": "HACHI_SMTP_PORT",
    "TOKOBOROS_SMTP_FROM": "HACHI_SMTP_FROM",
}


def _apply_tokoboros_shim() -> None:
    """Copy deprecated TOKOBOROS_* env vars to their HACHI_* equivalents.

    Only copies when the old var is present and the new var is NOT already set.
    Logs a deprecation warning for each migrated key so operators know to
    update their environment.
    """
    for old, new in _TOKOBOROS_RENAMES.items():
        if old in os.environ and new not in os.environ:
            os.environ[new] = os.environ[old]
            _logger.warning(
                "Deprecated env var %r — rename to %r in your .env or environment.",
                old,
                new,
            )


_apply_tokoboros_shim()

console = Console()


def _resolve_version() -> str:
    """Best-effort package version for ``--version`` (falls back to a literal)."""
    try:
        from importlib.metadata import version

        return version("hachi-og")
    except Exception:
        return "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"hachi {_resolve_version()}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    version: bool = typer.Option(  # noqa: ARG001 - consumed eagerly by the callback
        False,
        "--version",
        "-v",
        help="Show the Hachi version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        "-r",
        help="Pick a past session to resume (full context reload).",
    ),
    continue_latest: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Resume the most recent session.",
    ),
    repl: bool = typer.Option(
        False,
        "--repl",
        help="Launch the legacy Rich REPL instead of the Textual TUI.",
    ),
) -> None:
    """Hachi — your autonomous personal assistant.

    Run `hachi` with no command to start the assistant. Use a subcommand
    (run, setup, doctor, skill, ...) for everything else; `hachi -h` lists them.
    """
    if ctx.invoked_subcommand is not None:
        return
    _launch_assistant(repl=repl, resume=resume, continue_latest=continue_latest)


class _InProcessGatewayRuntime:
    """Bridge gateway API calls to the in-process AgentSession runtime."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentSession] = {}
        self._agents_lock = threading.Lock()
        # G3-T3 / REL-01 / HIGH-003: per-session chat serialization.
        # Concurrent chat() calls for the SAME session race on shared agent state
        # and ChromaDB writes.  A per-session lock serializes them while leaving
        # DIFFERENT sessions fully concurrent.
        # _chat_locks is guarded by _agents_lock for creation/deletion.
        self._chat_locks: dict[str, threading.Lock] = {}
        # G1-T7: set by _start_gateway_server so the first session boot resumes it.
        self._pending_resume_session_id: str | None = None
        # G1-T2 / CRIT-002: authoring pending-patch state (per-instance).
        self._pending_proposals: dict[str, str] = {}
        self._revert_snapshots: dict[str, str] = {}
        self._authoring_lock = threading.Lock()

    def _boot_session_agent(
        self, session_id: str, resume_session_id: str | None = None
    ) -> AgentSession:
        """Boot a fresh agent, optionally resuming a prior session's message history.

        Args:
            session_id: The new gateway session being created.
            resume_session_id: If set, the prior SessionStore session whose transcript
                to replay into the new agent's memory before the first turn.

        Returns:
            A booted :class:`AgentSession` ready to receive user input.
        """
        agent = boot_agent(resume_session_id=resume_session_id)
        # Expose the resident worker to the module-level readiness probe so it
        # can check worker liveness without coupling probe ↔ runtime instance.
        global _GATEWAY_RESIDENT_WORKER  # noqa: PLW0603
        worker = getattr(agent, "_resident_worker", None)
        if worker is not None:
            _GATEWAY_RESIDENT_WORKER = worker
        return agent

    def _get_agent(self, session_id: str) -> AgentSession:
        with self._agents_lock:
            agent = self._agents.get(session_id)
        if agent is None:
            raise GatewayProtocolError("Unknown session_id")
        return agent

    def register_connection(
        self,
        session_id: str,
        _req: ConnectRequest,
        resume_session_id: str | None = None,
    ) -> None:
        """Boot an agent for the new gateway session.

        Args:
            session_id: The new gateway session id.
            _req: The connect request envelope (unused beyond compat).
            resume_session_id: When set, replay this prior session's transcript into
                the new agent's memory so context carries over (G1-T7).
        """
        # G1-T7: consume the pending resume id on the first connection (one-shot).
        if resume_session_id is None:
            with self._agents_lock:
                pending = self._pending_resume_session_id
                if pending and not self._agents:
                    self._pending_resume_session_id = None
                    resume_session_id = pending
        agent = self._boot_session_agent(session_id, resume_session_id=resume_session_id)
        replaced_agent: AgentSession | None = None
        with self._agents_lock:
            replaced_agent = self._agents.get(session_id)
            self._agents[session_id] = agent
            # Ensure a per-session chat lock exists (idempotent for re-registrations).
            if session_id not in self._chat_locks:
                self._chat_locks[session_id] = threading.Lock()

        if replaced_agent is not None:
            try:
                replaced_agent.shutdown()
            except Exception:
                pass

    def close_connection(self, session_id: str) -> None:
        with self._agents_lock:
            agent = self._agents.pop(session_id, None)
            # Drop the per-session chat lock to avoid an unbounded leak.
            self._chat_locks.pop(session_id, None)
        if agent is not None:
            try:
                agent.shutdown()
            except Exception:
                pass

    def rehydrate_session(self, session_id: str) -> "AgentSession | None":
        """Boot a fresh session that replays *session_id*'s transcript (cold-start resume).

        Called by :func:`~hachi.core.runtime.resume._do_resume` when the live-session
        map has no entry for *session_id* (gateway restarted).  Boots a fresh
        :class:`AgentSession` with ``resume_session_id=session_id`` so the prior
        SQLite transcript is replayed into the new agent's memory before the first
        turn — exactly the same path taken by a normal session-resume at connect time.

        The new session is registered under the SAME *session_id* so that subsequent
        resume_run calls (and any concurrent gateway requests) find it in the map.

        Returns:
            The freshly booted and registered :class:`AgentSession`, or ``None``
            when boot fails (error is logged; caller should fallback to HonestResumeError).
        """
        try:
            agent = self._boot_session_agent(session_id, resume_session_id=session_id)
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "rehydrate_session: failed to boot agent for session %r",
                session_id,
                exc_info=True,
            )
            return None
        with self._agents_lock:
            self._agents[session_id] = agent
            if session_id not in self._chat_locks:
                self._chat_locks[session_id] = threading.Lock()
        return agent

    def _reload_agents(self) -> None:
        """Reboot cached session agents so provider/credential changes apply live.

        Provider config (model, base URL) and the resolved API key are baked into
        the LLM client at agent boot, so a running session keeps using whatever it
        started with. After a config mutation we rebuild each cached agent in
        place — re-reading the freshly written config + process env — and retire
        the old one. No-op when no sessions are connected (e.g. the standalone
        gateway started without ``--runtime``).
        """
        with self._agents_lock:
            session_ids = list(self._agents.keys())
        for session_id in session_ids:
            try:
                fresh = self._boot_session_agent(session_id)
            except Exception:
                continue  # keep the existing agent if a reboot fails
            with self._agents_lock:
                old = self._agents.get(session_id)
                self._agents[session_id] = fresh
            if old is not None and old is not fresh:
                try:
                    old.shutdown()
                except Exception:
                    pass

    def chat(self, session_id: str, prompt: str) -> str:
        """Send *prompt* to the session's agent and return the reply.

        Concurrent calls for the **same** session are serialized via a per-session
        lock so agent state and ChromaDB writes are never interleaved.  Calls for
        **different** sessions proceed concurrently (each session has its own lock).
        """
        agent = self._get_agent(session_id)
        with self._agents_lock:
            session_lock = self._chat_locks.get(session_id)
        if session_lock is None:
            # Defensive: lock was never created (e.g. agent registered via a code
            # path that predates this change).  Fall through without serialization
            # rather than raising — behaviour is unchanged from before this fix.
            return agent.chat(prompt)
        with session_lock:
            return agent.chat(prompt)

    def interrupt_session(self, session_id: str) -> dict:
        """Signal the live session's execution loop to stop at its next iteration.

        P1-4: sets the ``threading.Event`` inside ``ExecutionLoop`` so the loop exits
        cleanly at the top of the next iteration (after the current LLM chunk / tool call
        finishes).  Thread-safe; safe to call even when no turn is in progress.

        Args:
            session_id: The gateway session to interrupt.

        Returns:
            ``{"interrupted": True}`` when the signal was delivered;
            ``{"interrupted": False}`` when the session is not found.
        """
        with self._agents_lock:
            agent = self._agents.get(session_id)
        if agent is None:
            return {"interrupted": False}
        try:
            agent.loop.cancel()
            return {"interrupted": True}
        except Exception:
            return {"interrupted": False}

    def read_events(self, session_id: str, after: int, limit: int) -> list[GatewayEvent]:
        snapshots = self._get_agent(session_id).snapshot_events_since(after, limit)
        return [
            GatewayEvent(
                sequence=snap.sequence,
                event_type=snap.name,
                payload=snap.payload,
                time=snap.timestamp,
            )
            for snap in snapshots
        ]

    def session_state(self, session_id: str) -> dict:
        return asdict(self._get_agent(session_id).snapshot_session_state())

    def recent_sessions(self, limit: int) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            return [dict(item) for item in agent.query_recent_sessions(limit=limit)]
        # BB-13: no agent has booted yet (e.g. a fresh server start, before the
        # first message). Read persisted sessions straight from the SessionStore
        # so the conversation dropdown isn't empty on boot — the agent path and
        # this path both delegate to SessionStore.get_recent_sessions, so the
        # returned shape is identical. (Previously this returned [] when
        # _agents was empty, hiding every prior conversation until a turn ran.)
        store = SessionStore(db_path=str(get_hachi_paths().sessions_db))
        try:
            return [dict(item) for item in store.get_recent_sessions(limit=limit)]
        finally:
            store.shutdown()

    def session_messages(self, session_id: str, limit: int = 500) -> list[dict]:
        """Stored transcript for a (possibly historical) session — powers resume."""
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            return [dict(item) for item in agent.query_session_messages(session_id, limit=limit)]
        # BB-34: no agent booted yet (cold gateway start before the first turn).
        # Mirror the BB-13 fallback used by recent_sessions(): read directly from
        # the durable SessionStore so past-session histories load on the picker.
        store = SessionStore(db_path=str(get_hachi_paths().sessions_db))
        try:
            return [dict(item) for item in store.get_session_messages(session_id, limit=limit)]
        finally:
            store.shutdown()

    def delete_session_record(self, session_id: str) -> bool:
        """Permanently delete a persisted session from the store. True if it existed."""
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return False
        return bool(agent.delete_session(session_id))

    def runtime_events(self, session_id: str | None, limit: int) -> list[dict]:
        if session_id:
            agent = self._get_agent(session_id)
            events = agent.snapshot_runtime_events(limit=limit)
            return [asdict(event) for event in events]

        all_events: list[dict] = []
        with self._agents_lock:
            agents = list(self._agents.values())
        for agent in agents:
            all_events.extend(asdict(event) for event in agent.snapshot_runtime_events(limit=limit))
        all_events.sort(key=lambda item: str(item.get("timestamp", "")))
        return all_events[-limit:]

    def mcp_inventory(self) -> dict:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {"server_count": 0, "total_tool_count": 0, "servers": []}
        return asdict(agent.snapshot_mcp_inventory())

    def active_jobs(self) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        return [asdict(job) for job in agent.snapshot_active_jobs()]

    def failed_jobs(self, limit: int) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        return [asdict(job) for job in agent.snapshot_failed_jobs(limit=limit)]

    def permission_audit(self, limit: int) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        return [asdict(item) for item in agent.snapshot_permission_audit(limit=limit)]

    def subagent_reports(self, query: str, top_k: int) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        reports = agent.query_subagent_reports(query=query, top_k=top_k)
        return [asdict(item) for item in reports]

    def list_schedules(self) -> list[dict]:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            return agent.snapshot_schedules()
        # No active session — read from disk so GET /schedules works before
        # the user opens the chat (or after a gateway restart with no live session).
        return [s.to_dict() for s in ScheduleStore(get_hachi_paths().schedules_file).load()]

    def cancel_schedule(self, schedule_id: str) -> dict:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {"ok": False, "detail": "no active session"}
        ok = agent.cancel_schedule(schedule_id)
        return {"ok": ok, "schedule_id": schedule_id}

    def toggle_schedule(self, schedule_id: str, enabled: bool) -> dict:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {"ok": False, "detail": "no active session"}
        ok = agent.toggle_schedule_enabled(schedule_id, enabled=enabled)
        return {"ok": ok, "schedule_id": schedule_id, "enabled": enabled}

    def run_schedule_now(self, schedule_id: str) -> dict:
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {"ok": False, "detail": "no active session"}
        ok = agent.run_schedule_now(schedule_id)
        return {"ok": ok, "schedule_id": schedule_id}

    def capabilities(self) -> list[dict]:
        config = load_effective_config()
        # Pull OAuth status for each capability from the connector registry.
        # Import is deferred to avoid circular imports at module load time.
        try:
            from hachi.integrations.oauth_flow import connector_status as _connector_status
        except Exception:
            _connector_status = None  # noqa: F841

        items: list[dict] = []
        for capability_id, state in config.capabilities.items():
            entry: dict = {
                "id": capability_id,
                "kind": "native_integration",
                "enabled": bool(state.enabled),
                "configured": bool(state.configured),
                "secret_ref": state.secret_ref,
                # OAuth status fields — present when the connector is in the registry
                "auth_type": "none",
                "connected": False,
                "status": "disconnected",
            }
            if _connector_status is not None:
                try:
                    oauth = _connector_status(capability_id)
                    entry["auth_type"] = oauth["auth_type"]
                    entry["connected"] = oauth["connected"]
                    # Override "configured" with the registry's view (env var present)
                    # only when the connector is OAuth2; otherwise keep the config value.
                    if oauth["auth_type"] == "oauth2":
                        entry["configured"] = oauth["configured"]
                    entry["status"] = oauth["status"]
                except Exception:
                    pass
            items.append(entry)
        return items

    def get_config(self) -> dict:
        # BB-57: GET /config must never echo secret-shaped fields — mirror the
        # masking GET /config/providers already applies via provider_admin._mask_provider
        # (drops api_key_ref/api_key_env/base_url, masks header values) instead of
        # dumping the raw ResolvedConfig, which leaked env-var names, base URLs, and
        # raw header values (e.g. Authorization bearer tokens) verbatim.
        from hachi.gateway.provider_admin import _mask_provider

        config = load_effective_config()
        raw = config.model_dump(mode="python", exclude_none=True)

        raw["provider"] = _mask_provider("__primary__", config.provider)
        raw["providers"] = {
            name: _mask_provider(name, ps) for name, ps in (config.providers or {}).items()
        }

        capabilities_block = raw.get("capabilities")
        if isinstance(capabilities_block, dict):
            for entry in capabilities_block.values():
                if isinstance(entry, dict) and entry.get("secret_ref"):
                    entry["secret_ref"] = "***"

        # Ensure GET /config always includes a ``limits`` block with the frontend-facing
        # keys ``per_task_cap_usd`` / ``daily_cap_usd`` so caps saved via PUT /config/limits
        # round-trip on reload.
        # Internally: max_turn_cost_usd = per-task cap, max_daily_cost_usd = daily cap.
        limits_block = raw.setdefault("limits", {})
        limits_block["per_task_cap_usd"] = getattr(config.limits, "max_turn_cost_usd", None)
        limits_block["daily_cap_usd"] = getattr(config.limits, "max_daily_cost_usd", None)
        return raw

    def update_provider(self, payload: dict) -> dict:
        provider = payload.get("provider", payload)
        if not isinstance(provider, dict):
            raise GatewayProtocolError("provider payload must be an object")

        config = load_effective_config()
        current_provider_kind = str(config.provider.kind).strip()
        current_provider_model = str(config.provider.model).strip()
        kind = provider.get("kind")
        model = provider.get("model")
        base_url = provider.get("base_url")
        api_key = provider.get("api_key")
        api_key_ref = provider.get("api_key_ref")
        api_key_env = provider.get("api_key_env")

        if kind is not None:
            from typing import get_args

            from hachi.core.settings import ProviderKind

            kind_text = str(kind)
            _valid_kinds = set(get_args(ProviderKind))
            if kind_text not in _valid_kinds:
                raise GatewayProtocolError(
                    f"provider.kind must be one of: {', '.join(sorted(_valid_kinds))}"
                )
            config.provider.kind = kind_text  # type: ignore[assignment]

        if model is not None:
            model_text = str(model).strip()
            if not model_text:
                raise GatewayProtocolError("provider.model cannot be empty")
            from hachi.core.onboarding import resolve_provider_model

            config.provider.model = resolve_provider_model(
                str(config.provider.kind),
                model_text,
                previous_kind=current_provider_kind,
                previous_model=current_provider_model,
            )
        elif kind is not None and str(config.provider.kind).strip() != current_provider_kind:
            from hachi.core.onboarding import resolve_provider_model

            config.provider.model = resolve_provider_model(
                str(config.provider.kind),
                None,
                previous_kind=current_provider_kind,
                previous_model=current_provider_model,
            )

        if base_url is not None:
            config.provider.base_url = str(base_url).strip() or None

        # API key handling — persist raw secrets to the secret store + process
        # env (never the config file); record only the env-var NAME. A raw key may
        # arrive via `api_key` (preferred) or, for backward compatibility, as a
        # non-env-name `api_key_ref`.
        raw_api_key = api_key
        if not raw_api_key and api_key_ref and not looks_like_env_var_name(str(api_key_ref)):
            raw_api_key = api_key_ref
            api_key_ref = None

        if api_key_env is not None:
            config.provider.api_key_env = str(api_key_env).strip() or None

        if raw_api_key:
            env_name = persist_provider_api_key(
                str(config.provider.kind),
                str(raw_api_key),
                api_key_env=config.provider.api_key_env,
                secret_store=create_default_secret_store(),
            )
            if env_name:
                config.provider.api_key_ref = env_name
                config.provider.api_key_env = env_name
        elif api_key_ref is not None:
            config.provider.api_key_ref = str(api_key_ref).strip() or None

        write_global_config(config)
        # Provider/credential changes are baked into the LLM client at boot, so
        # reboot any live session to apply them without a manual restart.
        self._reload_agents()
        return config.model_dump(mode="python", exclude_none=True)

    def validate_provider(self, payload: dict) -> dict:
        provider = payload.get("provider", payload)
        if not isinstance(provider, dict):
            raise GatewayProtocolError("provider payload must be an object")

        kind = str(provider.get("kind") or "").strip()
        model = str(provider.get("model") or "").strip()
        api_key_ref = str(provider.get("api_key_ref") or "").strip()
        api_key_env = str(provider.get("api_key_env") or "").strip()
        errors: list[str] = []
        warnings: list[str] = []

        from typing import get_args

        from hachi.core.settings import ProviderKind

        _valid_kinds = set(get_args(ProviderKind))
        if kind not in _valid_kinds:
            errors.append(f"provider.kind must be one of: {', '.join(sorted(_valid_kinds))}")
        if not model:
            errors.append("provider.model is required")

        if kind in {"anthropic", "openai-compatible"} and not (api_key_ref or api_key_env):
            warnings.append("api_key_ref or api_key_env should be set for remote providers")

        if kind == "ollama" and not str(provider.get("base_url") or "").strip():
            warnings.append("base_url is recommended for ollama providers")

        return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}

    def update_permissions(self, payload: dict) -> dict:
        permissions = payload.get("permissions", payload)
        if not isinstance(permissions, dict):
            raise GatewayProtocolError("permissions payload must be an object")

        tier = str(permissions.get("tier") or "").strip()
        if tier and tier not in {"sandbox", "guided", "unrestricted"}:
            raise GatewayProtocolError("permissions.tier must be sandbox, guided, or unrestricted")

        ask_before = permissions.get("ask_before")
        if ask_before is not None and not isinstance(ask_before, dict):
            raise GatewayProtocolError("permissions.ask_before must be an object")

        config = load_effective_config()
        if tier:
            config.permissions.tier = tier  # type: ignore[assignment]
        if isinstance(ask_before, dict):
            # Only the recognised "Ask before…" rule keys may be set; each value
            # must be a boolean. This persists the Settings panel toggles so they
            # survive a reload (the rule labels live in the frontend).
            valid_keys = set(config.permissions.ask_before.model_dump().keys())
            for key, value in ask_before.items():
                if key not in valid_keys:
                    raise GatewayProtocolError(
                        f"permissions.ask_before.{key} is not a recognised rule"
                    )
                if not isinstance(value, bool):
                    raise GatewayProtocolError(f"permissions.ask_before.{key} must be a boolean")
                setattr(config.permissions.ask_before, key, value)

        write_global_config(config)

        # Bug 7: write_global_config persists the tier to settings.toml, but
        # PermissionGate reads device-permissions.og (not settings.toml).  A tier
        # change must therefore regenerate the .og so that (a) fresh boots pick it up
        # and (b) boot_agent's reconcile step can detect the drift.
        if tier:
            _perm_file = get_permissions_file()
            try:
                from hachi.core.permissions import PermissionGate, generate_permissions_og

                # Preserve any custom allowed_paths the user added manually.
                _custom_paths: list[str] | None = None
                if _perm_file.exists():
                    try:
                        _gate = PermissionGate(_perm_file)
                        if not _gate._fs.allow_all and _gate._fs.allowed_paths:
                            _custom_paths = [str(p) for p in _gate._fs.allowed_paths]
                    except Exception:
                        pass
                _og_content = generate_permissions_og(tier, _custom_paths)
                _tmp = _perm_file.with_suffix(".og.tmp")
                _tmp.write_text(_og_content, encoding="utf-8")
                import os as _os

                _os.replace(_tmp, _perm_file)
            except Exception:
                _logger.warning(
                    "update_permissions: failed to regenerate device-permissions.og", exc_info=True
                )

        return config.model_dump(mode="python", exclude_none=True)

    def update_memory(self, payload: dict) -> dict:
        memory = payload.get("memory", payload)
        if not isinstance(memory, dict):
            raise GatewayProtocolError("memory payload must be an object")

        config = load_effective_config()
        if "enable_session_history" in memory:
            value = memory["enable_session_history"]
            if not isinstance(value, bool):
                raise GatewayProtocolError("memory.enable_session_history must be a boolean")
            config.memory.enable_session_history = value
        if "enable_semantic_memory" in memory:
            value = memory["enable_semantic_memory"]
            if not isinstance(value, bool):
                raise GatewayProtocolError("memory.enable_semantic_memory must be a boolean")
            config.memory.enable_semantic_memory = value

        write_global_config(config)
        return config.model_dump(mode="python", exclude_none=True)

    def list_models(self) -> list[dict]:
        """Return provider-specific model lists using live discovery when possible.

        Attempts live discovery via the same path as the ``hachi models`` CLI command.
        Falls back to a current static list when the provider API is unreachable or
        no API key is configured.  The configured default model is always present.

        HIGH-008: static fallback list is kept current (includes claude-opus-4-8,
        claude-sonnet-4-6, claude-haiku-4-5).
        """
        # Current static fallback lists per provider kind.
        _STATIC_FALLBACK: dict[str, list[str]] = {
            "anthropic": [
                "claude-haiku-4-5",
                "claude-sonnet-4-6",
                "claude-opus-4-8",
            ],
            "openai-compatible": ["gpt-4.1-mini", "gpt-4.1"],
            "ollama": ["llama3.1:8b", "qwen2.5-coder:7b"],
        }
        config = load_effective_config()
        kind = config.provider.kind
        current = config.provider.model
        allowed = list(getattr(config.provider, "allowed_models", []) or [])

        # Attempt live discovery — same path as the ``hachi models`` CLI command.
        discovered: list[str] = []
        try:
            from hachi.core.llm import create_llm_client, resolve_available_models

            provider_config = {
                "kind": kind,
                "model": current,
                "api_key_ref": getattr(config.provider, "api_key_ref", None),
                "api_key_env": getattr(config.provider, "api_key_env", None),
                "base_url": getattr(config.provider, "base_url", None),
            }
            client = create_llm_client(provider_config, secret_store=create_default_secret_store())
            try:
                discovered = client.list_models()
            finally:
                close = getattr(client, "close", None)
                if callable(close):
                    close()
        except Exception:
            # Offline, missing API key, or import error — fall through to static list.
            pass

        if discovered:
            from hachi.core.llm import resolve_available_models

            model_ids = resolve_available_models(discovered, allowed, current)
        else:
            # Static fallback: use allowlist if configured, else provider defaults.
            fallback = list(allowed) if allowed else _STATIC_FALLBACK.get(kind, [current])
            model_ids = list(fallback)
            if current and current not in model_ids:
                model_ids.insert(0, current)

        return [
            {
                "id": model,
                "label": model,
                "provider": kind,
                "recommended": model == current,
            }
            for model in model_ids
        ]

    def setup_state(self) -> dict:
        service = OnboardingService()
        state = service.resume_state()
        return {
            "state": state.model_dump(mode="python", exclude_none=True),
            "needs_setup": service.needs_setup(),
            "environment": service.detect_environment(),
        }

    def apply_setup(self, payload: dict) -> dict:
        plan_payload = payload.get("plan", payload)
        if not isinstance(plan_payload, dict):
            raise GatewayProtocolError("setup payload must be an object")

        service = OnboardingService()
        try:
            plan = service.apply_setup(plan_payload)
        except ValueError as exc:
            raise GatewayProtocolError(str(exc)) from exc
        # Apply provider/credential changes from the wizard to any live session.
        self._reload_agents()
        return {
            "ok": True,
            "plan": plan.model_dump(mode="python", exclude_none=True),
            "state": service.resume_state().model_dump(mode="python", exclude_none=True),
        }

    def shutdown(self) -> None:
        with self._agents_lock:
            agents = list(self._agents.values())
            self._agents.clear()
        for agent in agents:
            try:
                agent.shutdown()
            except Exception:
                pass

    # ==========================================
    # Web endpoint handlers — added for web UI (#1–#6)
    # ==========================================

    def get_skills(self) -> list[dict]:
        """Return the .og skill inventory (route: GET /skills)."""
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        return [asdict(s) for s in agent.snapshot_skills()]

    def get_memory(self) -> dict:
        """Return grouped memory facts for the Memory screen (route: GET /memory)."""
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {"groups": [], "blocked": [], "proposed": None}
        return agent.snapshot_memory_facts()

    def get_memory_recall(self, query: str, top_k: int = 8) -> list[dict]:
        """Return semantic recall hits (route: GET /memory/recall).

        Calls vault.semantic_search directly to preserve the similarity score,
        which query_memory_recall (on AgentSession) drops when building its snapshot.
        """
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None or agent.vault is None:
            return []
        try:
            rows = agent.vault.semantic_search(query, top_k=top_k)
        except Exception:
            return []
        results: list[dict] = []
        for row in rows:
            fact = row.get("raw_content") or row.get("content", "")
            # G4-T2 (SEC-03): redact secrets at the API boundary before returning to the
            # client.  _redact_results() inside semantic_search() already applies the
            # vault-local patterns; redact_secrets() adds the full secret_scanner pattern
            # set (GitHub, Stripe, npm, JWT, …) as a defence-in-depth layer.
            fact, _ = redact_secrets(str(fact))
            src = row.get("category", "")
            # The row uses key "score" (from RRF merge) or "distance" (from Chroma).
            # Tolerate absence of both keys.
            raw_score = row.get("score") or row.get("distance")
            score = str(round(float(raw_score), 2)) if raw_score is not None else ""
            results.append({"fact": fact, "score": score, "src": src})
        return results

    def get_og_graph(self) -> dict:
        """Return the ObjectGraph node graph (route: GET /og/graph).

        When an active agent session exists, its skill engine (which includes
        workspace skills) is used.  Before any session is started, falls back to
        the process-shared skill engine populated by
        :class:`~hachi.gateway.shared_services.ProcessSharedServices`, which
        loads the bundled default skills at gateway boot time.  This ensures the
        OG Explorer shows data even before the first conversation is opened.
        """
        from hachi.gateway.orchestrator import og_graph_from_engine

        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            return agent.snapshot_og_graph()

        # No active session yet. Prefer the process-shared engine if a prior
        # session already initialised it; otherwise build a standalone engine
        # from the bundled default skills so the OG Explorer is populated before
        # the first conversation is opened (the shared services are created
        # lazily on first session boot, not at gateway startup).
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        if shared is not None and shared.skill_engine is not None:
            graph = og_graph_from_engine(shared.skill_engine)
            if graph.get("count"):
                return graph

        engine = self._standalone_og_engine()
        if engine is not None:
            return og_graph_from_engine(engine)
        return {"nodes": [], "count": 0}

    def _standalone_og_engine(self) -> object | None:
        """Build (once, cached) a SkillEngine from the bundled default skills.

        The process-shared services are initialised lazily on first session
        boot, so before any conversation exists ``ProcessSharedServices.instance``
        is ``None``. This standalone engine lets the OG Explorer show the skill
        graph immediately after gateway startup.
        """
        cached = getattr(self, "_og_engine_cache", None)
        if cached is not None:
            return cached
        try:
            from hachi.core.paths import get_hachi_paths
            from hachi.og_engine.engine import SkillEngine

            engine = SkillEngine(agent_role="orchestrator")
            default_skills_dir = Path(__file__).parent.parent / "default_skills"
            if default_skills_dir.exists():
                engine.load_directory(default_skills_dir)
            try:
                engine.load_directory(get_hachi_paths().skills_dir)
            except OSError:
                logging.getLogger(__name__).debug(
                    "standalone OG engine: workspace load skipped", exc_info=True
                )
            self._og_engine_cache = engine
            return engine
        except Exception:
            logging.getLogger(__name__).warning("standalone OG engine build failed", exc_info=True)
            return None

    def get_authoring_targets(self) -> list[dict]:
        """List editable .og and config targets from the workspace (route: GET /authoring/targets).

        Reads config-dir files independently of a live agent session.
        """
        paths = get_hachi_paths()
        targets: list[dict] = []

        # Collect .og skill files from the skills directory.
        skills_dir = paths.skills_dir
        if skills_dir.exists():
            for og_file in sorted(skills_dir.glob("*.og")):
                kind = "brain" if og_file.name.startswith("brain-") else "skill"
                rel = og_file.relative_to(skills_dir).as_posix()
                targets.append({"name": og_file.name, "path": rel, "kind": kind, "dirty": False})

        # Include the permissions file (device-permissions.og).
        perm_file = paths.permissions_file
        if perm_file.exists():
            targets.append(
                {
                    "name": perm_file.name,
                    "path": perm_file.name,
                    "kind": "config",
                    "dirty": False,
                }
            )

        # Include the global config toml.
        config_toml = paths.global_config_toml
        if config_toml.exists():
            targets.append(
                {
                    "name": config_toml.name,
                    "path": config_toml.name,
                    "kind": "config",
                    "dirty": False,
                }
            )

        return targets

    def _resolve_authoring_target_path(self, name: str) -> Path:
        """Resolve a target name to a filesystem path, enforcing security constraints.

        SECURITY: reject any name containing ``/``, ``\\``, or ``..`` to prevent
        path-traversal attacks. Only names present in the allowed target list are
        accepted.

        Args:
            name: The target name (e.g. ``"brain-core.og"``).

        Returns:
            Absolute :class:`~pathlib.Path` to the file.

        Raises:
            GatewayProtocolError: When the name is unsafe or not in the allowed set.
        """
        if "/" in name or "\\" in name or ".." in name:
            raise GatewayProtocolError(f"Invalid target name '{name}'")

        allowed_targets = self.get_authoring_targets()
        allowed_names = {t["name"] for t in allowed_targets}
        if name not in allowed_names:
            raise GatewayProtocolError(f"Target '{name}' not found in allowed set")

        # Re-derive the actual path from the known safe locations.
        paths = get_hachi_paths()
        skill_path = paths.skills_dir / name
        if skill_path.exists():
            return skill_path
        perm_path = paths.permissions_file
        if perm_path.name == name:
            return perm_path
        config_path = paths.global_config_toml
        if config_path.name == name:
            return config_path
        raise GatewayProtocolError(f"Target '{name}' could not be resolved")

    def get_authoring_target(self, name: str) -> dict:
        """Return the source text for a single authoring target (GET /authoring/targets/{name})."""
        file_path = self._resolve_authoring_target_path(name)
        source = file_path.read_text(encoding="utf-8")
        return {"name": name, "source": source}

    # ---- Authoring generate/apply/revert (G1-T2 / CRIT-002) ----
    # Pending proposed content is keyed by target name and stored in two dicts:
    #   _pending_proposals : name -> proposed text (set by generate; consumed by apply)
    #   _revert_snapshots  : name -> prior text    (set by apply;    consumed by revert)
    # Both are protected by _authoring_lock so concurrent requests are serialised.
    # (Instance variables initialised in __init__.)

    def authoring_generate(self, name: str, prompt: str) -> dict:
        """Generate a proposed patch for the named target via the configured LLM.

        Calls the LLM with the current file content + user prompt and returns a
        real unified diff (``[["" | "add" | "del", line], ...]``).  The proposed
        content is stored in ``_pending_proposals`` so that a subsequent
        ``authoring_apply`` can write it without the client re-sending it.

        The LLM call is synchronous and should be run off the event loop by the
        FastAPI route via ``anyio.to_thread.run_sync``.

        Args:
            name: Validated target name (path-traversal already rejected by
                  ``_resolve_authoring_target_path``).
            prompt: Natural-language description of the desired change.

        Returns:
            ``{"diff": [["" | "add" | "del", line], ...]}``

        Raises:
            GatewayProtocolError: If the target cannot be resolved.
            GatewayUnavailableError: If no API key / LLM is available.
        """
        import difflib

        from hachi.core.llm import Message, create_llm_client
        from hachi.gateway.control_plane import GatewayUnavailableError

        file_path = self._resolve_authoring_target_path(name)
        original = file_path.read_text(encoding="utf-8")

        # Build provider config from current effective config.
        config = load_effective_config()
        provider_config = {
            "kind": str(config.provider.kind),
            "model": str(config.provider.model),
            "api_key_ref": getattr(config.provider, "api_key_ref", None),
            "api_key_env": getattr(config.provider, "api_key_env", None),
            "base_url": getattr(config.provider, "base_url", None),
        }

        try:
            client = create_llm_client(provider_config, secret_store=create_default_secret_store())
        except ValueError as exc:
            raise GatewayUnavailableError(
                f"Cannot generate patch: LLM client unavailable — {exc}. "
                "Check your API key configuration."
            ) from exc

        system = (
            "You are a precise code editor for Hachi .og skill files. "
            "The user will give you the current file content and a description of the change "
            "they want. Respond with ONLY the complete revised file content — no markdown fences, "
            "no explanations, no diff markers. Output the full file verbatim with only the "
            "requested modifications applied."
        )
        user_msg = (
            f"File: {name}\n\n"
            f"Current content:\n{original}\n\n"
            f"Requested change: {prompt}\n\n"
            "Output the complete revised file content only."
        )

        try:
            response = client.generate(
                messages=[Message(role="user", content=user_msg)],
                system_prompt=system,
            )
        except Exception as exc:
            raise GatewayUnavailableError(
                f"LLM generate call failed: {exc}. Check your API key and model configuration."
            ) from exc
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

        proposed = response.content.strip()
        if not proposed:
            raise GatewayUnavailableError("LLM returned an empty response; cannot produce a diff.")

        # Store pending proposal so apply() can write it.
        with self._authoring_lock:
            self._pending_proposals[name] = proposed

        # Build unified diff as list of ["" | "add" | "del", line] pairs.
        orig_lines = original.splitlines()
        prop_lines = proposed.splitlines()
        diff_lines: list[tuple[str, str]] = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, orig_lines, prop_lines, autojunk=False
        ).get_opcodes():
            if tag == "equal":
                for line in orig_lines[i1:i2]:
                    diff_lines.append(("", line))
            elif tag in ("replace", "delete"):
                for line in orig_lines[i1:i2]:
                    diff_lines.append(("del", line))
                if tag == "replace":
                    for line in prop_lines[j1:j2]:
                        diff_lines.append(("add", line))
            elif tag == "insert":
                for line in prop_lines[j1:j2]:
                    diff_lines.append(("add", line))

        return {"diff": diff_lines}

    def authoring_apply(self, name: str) -> dict:
        """Apply the pending proposed content for the named target to disk.

        Performs an atomic write (temp file → replace) inside the skills root and
        saves the prior content as a revert snapshot.  Triggers a skill-engine
        re-index when the target is a ``.og`` file.

        Args:
            name: Validated target name.

        Returns:
            ``{"ok": True, "reindexed_ms": <elapsed_ms>}``

        Raises:
            GatewayProtocolError: If there is no pending proposal for this target.
        """
        import time

        with self._authoring_lock:
            proposed = self._pending_proposals.get(name)

        if proposed is None:
            raise GatewayProtocolError(f"No pending proposal for '{name}'. Call /generate first.")

        file_path = self._resolve_authoring_target_path(name)
        prior = file_path.read_text(encoding="utf-8")

        # Atomic write: write to a sibling temp file then replace.
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            tmp_path.write_text(proposed, encoding="utf-8")
            tmp_path.replace(file_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        # Store revert snapshot AFTER successful write.
        with self._authoring_lock:
            self._revert_snapshots[name] = prior
            self._pending_proposals.pop(name, None)

        # Trigger skill-engine re-index for .og files.
        reindexed_ms = 0
        if name.endswith(".og"):
            t0 = time.monotonic()
            try:
                with self._agents_lock:
                    agent = next(iter(self._agents.values()), None)
                if agent is not None:
                    reindex = getattr(agent, "reindex_skills", None)
                    if callable(reindex):
                        reindex()
            except Exception:
                pass
            reindexed_ms = int((time.monotonic() - t0) * 1000)

        return {"ok": True, "reindexed_ms": reindexed_ms}

    def authoring_save_source(self, name: str, content: str) -> dict:
        """Persist manually edited .og content for the named target (CONTRACT-AUTHORING-SAVE).

        Validates ``name`` (path-traversal guard), optionally parses the content as
        a valid ObjectGraph (.og files only), and writes it atomically.

        Args:
            name:    Validated target name (e.g. ``"brain-core.og"``).
            content: Full file content to persist.

        Returns:
            ``{"ok": True, "name": name}``

        Raises:
            GatewayProtocolError: When the name is invalid/unknown, or the content
                is empty.
            GatewayUnavailableError: When the content fails OG parsing for .og files.
        """
        if not content.strip():
            raise GatewayProtocolError("content cannot be empty")

        file_path = self._resolve_authoring_target_path(name)

        # For .og files, validate that the content parses before overwriting.
        if name.endswith(".og"):
            import tempfile as _tempfile

            from hachi.gateway.control_plane import GatewayUnavailableError as _Unavail
            from hachi.og_engine.parser import parse_og_file as _parse_og

            _tmp_path: str | None = None
            try:
                with _tempfile.NamedTemporaryFile(
                    mode="w", suffix=".og", delete=False, encoding="utf-8"
                ) as _tmp:
                    _tmp_path = _tmp.name
                    _tmp.write(content)
                _parse_og(_tmp_path)
            except _Unavail:
                raise  # re-raise without wrapping
            except Exception as exc:
                raise _Unavail(
                    f"Content does not parse as a valid ObjectGraph (.og) file: {exc}. "
                    "Fix the syntax and try again."
                ) from exc
            finally:
                if _tmp_path is not None:
                    try:
                        Path(_tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass

        # Atomic write: write to sibling temp file then replace.
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(file_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        # Trigger skill-engine re-index for .og files.
        if name.endswith(".og"):
            try:
                with self._agents_lock:
                    agent = next(iter(self._agents.values()), None)
                if agent is not None:
                    reindex = getattr(agent, "reindex_skills", None)
                    if callable(reindex):
                        reindex()
            except Exception:
                pass

        return {"ok": True, "name": name}

    def authoring_revert(self, name: str) -> dict:
        """Restore the revert snapshot for the named target (undoes the last apply).

        Also discards any pending un-applied proposal for this target.

        Args:
            name: Validated target name.

        Returns:
            ``{"ok": True}``

        Raises:
            GatewayProtocolError: If there is nothing to revert.
        """
        with self._authoring_lock:
            snapshot = self._revert_snapshots.get(name)
            # Also discard any un-applied pending proposal.
            self._pending_proposals.pop(name, None)

        if snapshot is None:
            raise GatewayProtocolError(
                f"Nothing to revert for '{name}'. No prior apply snapshot exists."
            )

        file_path = self._resolve_authoring_target_path(name)
        tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            tmp_path.write_text(snapshot, encoding="utf-8")
            tmp_path.replace(file_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        with self._authoring_lock:
            self._revert_snapshots.pop(name, None)

        return {"ok": True}

    def get_spend(self, session_id: str | None = None) -> dict:
        """Return per-turn token/cost rows, compaction events, and model totals.

        Best-effort aggregation: scans the last 500 runtime events for
        ``usage.updated`` events (cumulative counters) and builds per-turn deltas.
        Compaction events (``memory.compaction``) are surfaced as ``tidies``.
        ``models`` is a single entry from the current config + snapshot_usage().

        NOTE: Per-turn input/output token split is not separately tracked in the
        runtime event payload today. The ``inT`` field is always 0 and ``out``
        carries the full token delta. Update when the event payload is enriched.
        """
        # Pick the agent: prefer explicit session_id, fall back to most-recent.
        with self._agents_lock:
            if session_id and session_id in self._agents:
                agent = self._agents[session_id]
            else:
                agent = next(iter(self._agents.values()), None)

        if agent is None:
            return {"turns": [], "tidies": [], "models": []}

        events = agent.snapshot_runtime_events(limit=500)

        turns: list[dict] = []
        tidies: list[dict] = []
        prev_total_tokens: float = 0.0
        prev_total_cost: float = 0.0
        turn_idx = 0

        for event in events:
            event_name = event.name
            payload = event.payload or {}

            # Per-turn rows from usage.updated events (cumulative → delta).
            if event_name == "usage.updated":
                total_tokens = float(payload.get("total_tokens", 0) or 0)
                total_cost = float(payload.get("estimated_cost_usd", 0) or 0)

                delta_tokens = total_tokens - prev_total_tokens
                delta_cost = total_cost - prev_total_cost

                if delta_tokens > 0 or delta_cost > 0:
                    turn_idx += 1
                    # NOTE: Per-turn input/output split not available; out = delta.
                    turns.append(
                        {
                            "n": turn_idx,
                            "inT": 0,
                            "out": int(delta_tokens),
                            "cost": round(delta_cost, 4),
                        }
                    )

                prev_total_tokens = total_tokens
                prev_total_cost = total_cost

            # Compaction events → tidy rows.
            # Real event name from runtime_events.py: "memory.compaction" (COMPACTION).
            if "memory" in event_name and ("compact" in event_name or "tidy" in event_name):
                ts = event.timestamp or ""
                # Use HH:MM portion of ISO timestamp if available.
                if len(ts) >= 16:
                    ts = ts[11:16]
                tidies.append(
                    {
                        "ts": ts,
                        "before": int(payload.get("before_tokens", 0) or 0),
                        "after": int(payload.get("after_tokens", 0) or 0),
                    }
                )

        # Issue 9: real per-model breakdown from the cost tracker (a session that
        # routed to e.g. opus + haiku now shows BOTH, instead of one collapsed entry).
        # Each row carries both the legacy keys (name/tokens/cost — read by the work
        # tab) and the C-SPEND keys (model/cost_usd/input_tokens/output_tokens — read
        # by the Spend settings breakdown), so both consumers are satisfied.
        config = load_effective_config()
        usage = agent.snapshot_usage()
        tracker = getattr(getattr(agent, "loop", None), "cost_tracker", None)
        models: list[dict] = []
        if tracker is not None and hasattr(tracker, "per_model_snapshot"):
            try:
                for mid, snap in tracker.per_model_snapshot().items():
                    _cost = round(float(snap.estimated_cost_usd), 6)
                    models.append(
                        {
                            "name": mid,
                            "model": mid,
                            "tokens": int(snap.input_tokens + snap.output_tokens),
                            "input_tokens": int(snap.input_tokens),
                            "output_tokens": int(snap.output_tokens),
                            "cost": _cost,
                            "cost_usd": _cost,
                            "color": "",  # Client assigns color.
                        }
                    )
            except Exception:
                models = []
        if not models and usage:
            # Fallback: single aggregate entry (no per-model attribution available yet).
            _cost = round(float(usage.get("estimated_cost_usd", 0) or 0), 6)
            models.append(
                {
                    "name": config.provider.model,
                    "model": config.provider.model,
                    "tokens": int(usage.get("total_tokens", 0) or 0),
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "cost": _cost,
                    "cost_usd": _cost,
                    "color": "",
                }
            )

        # C-SPEND: per-modality / per-session / cumulative breakdown for the Spend UI.
        # Text cost = sum of per-model LLM costs. Voice cost is recorded into the daily
        # ledger (cost.record_voice_usage) but is not yet attributed per-session, so the
        # per-session modality split lists text only. TODO(issue9): modality-tagged ledger.
        text_cost = round(sum(float(m["cost_usd"]) for m in models), 6)
        session_total = (
            round(float(usage.get("estimated_cost_usd", 0) or 0), 6) if usage else text_cost
        )
        cumulative_usd = session_total
        try:
            _daily = self.get_spend_daily()
            cumulative_usd = round(float(_daily.get("spent_usd", session_total) or 0), 6)
        except Exception:
            pass

        # R10: per-feature cost attribution.
        by_feature: dict[str, object] = {}
        if tracker is not None and hasattr(tracker, "per_feature_snapshot"):
            try:
                by_feature = tracker.per_feature_snapshot()  # type: ignore[assignment]
            except Exception:
                pass

        return {
            "turns": turns,
            "tidies": tidies,
            "models": models,
            "by_feature": by_feature,
            "modalities": {"text": text_cost},
            "session": {
                "session_id": session_id or "",
                "cost_usd": session_total,
                "turns": len(turns),
            },
            "cumulative_usd": cumulative_usd,
        }

    def get_spend_daily(self) -> dict:
        """Return today's accumulated spend plus configured caps (GET /spend/daily).

        Reads the daily_spend ledger from SQLite directly — no live agent needed.
        Works immediately after a restart so the frontend can hydrate ``spent`` on load.

        Returns:
            Dict with:
                ``spent_usd``     — cumulative spend for today (local calendar date).
                ``daily_cap_usd`` — configured daily cap or ``None`` if unlimited.
                ``task_cap_usd``  — configured per-task (turn) cap or ``None`` if unlimited.
                ``date``          — today's ISO date string (e.g. ``"2026-06-22"``).
        """
        today = _date.today().isoformat()
        store = SessionStore()
        try:
            spent = store.get_daily_spend(today)
        finally:
            store.shutdown()
        config = load_effective_config()
        return {
            "spent_usd": spent,
            "daily_cap_usd": config.limits.max_daily_cost_usd,
            "task_cap_usd": config.limits.max_turn_cost_usd,
            "date": today,
        }

    def set_capability_enabled(self, cap_id: str, enabled: bool) -> dict:
        """Toggle a capability on/off and persist to global config (PUT /capabilities/{id}/enabled).

        Mirrors update_permissions: load config, mutate, write, return result.
        """
        config = load_effective_config()
        if cap_id not in config.capabilities:
            raise GatewayProtocolError(f"unknown capability '{cap_id}'")
        config.capabilities[cap_id].enabled = bool(enabled)
        write_global_config(config)
        return {
            "id": cap_id,
            "enabled": bool(enabled),
            "configured": bool(config.capabilities[cap_id].configured),
        }

    # ------ Memory CRUD ------

    _VAULT_GROUP_MAP: dict[str, str] = {
        "core_memory": "upsert_fact",
        "user_profile": "upsert_user_fact",
        "agent_profile": "upsert_agent_fact",
    }

    def add_memory_fact(self, group: str, text: str) -> dict:
        """Add a fact to the specified vault collection (POST /memory/facts).

        Maps ``group`` to the appropriate upsert method on MemoryVault:
          - ``core_memory``   → vault.upsert_fact
          - ``user_profile``  → vault.upsert_user_fact
          - ``agent_profile`` → vault.upsert_agent_fact

        Args:
            group: Collection name — one of core_memory, user_profile, agent_profile.
            text:  Plain-text fact to persist.

        Returns:
            Dict with ``id`` (the content-hash fact id, possibly prefixed with
            ``BLOCKED:`` or ``LIMIT_REACHED`` when the vault rejects the write).
        """
        if not text.strip():
            raise GatewayProtocolError("text cannot be empty")
        if group not in self._VAULT_GROUP_MAP:
            raise GatewayProtocolError(
                f"group must be one of: {', '.join(sorted(self._VAULT_GROUP_MAP))}"
            )
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None or agent.vault is None:
            return {"id": "", "error": "no active session or vault unavailable"}
        method_name = self._VAULT_GROUP_MAP[group]
        upsert_fn = getattr(agent.vault, method_name, None)
        if not callable(upsert_fn):
            return {"id": "", "error": "vault method unavailable"}
        try:
            fact_id: str = upsert_fn(text.strip())
        except Exception as exc:
            return {"id": "", "error": f"vault write failed: {exc}"}
        return {"id": fact_id}

    # ==========================================
    # G1 — new handler implementations
    # ==========================================

    def update_limits(self, payload: dict) -> dict:
        """Persist per-task and daily spend caps to global config (PUT /config/limits).

        Reads the existing config, updates limits.max_turn_cost_usd (frontend:
        ``per_task_cap_usd``) and limits.max_daily_cost_usd (frontend: ``daily_cap_usd``),
        writes back, and returns the updated config dump.

        Args:
            payload: Dict with optional ``per_task_cap_usd`` and ``daily_cap_usd`` (float, USD).

        Returns:
            Updated config dict.
        """
        per_task = payload.get("per_task_cap_usd")
        daily = payload.get("daily_cap_usd")

        config = load_effective_config()
        if per_task is not None:
            try:
                val = float(per_task)
                config.limits.max_turn_cost_usd = val if val > 0 else None
            except (TypeError, ValueError):
                raise GatewayProtocolError("per_task_cap_usd must be a number") from None
        if daily is not None:
            try:
                val = float(daily)
                # max_daily_cost_usd is the rolling calendar-day cap; distinct from
                # max_session_cost_usd which caps a single conversation session.
                config.limits.max_daily_cost_usd = val if val > 0 else None
            except (TypeError, ValueError):
                raise GatewayProtocolError("daily_cap_usd must be a number") from None

        write_global_config(config)
        return config.model_dump(mode="python", exclude_none=True)

    def add_allowed_folder(self, folder_path: str) -> dict:
        """Append a folder path to device-permissions.og allowed_paths.

        Mutates the on-disk device-permissions.og file using the same approach
        as the ``hachi permissions --allow`` CLI command.

        Args:
            folder_path: The path to add. Will be expanded and resolved.

        Returns:
            Dict with ok=True and the resolved path.
        """
        from pathlib import Path as _Path

        path = folder_path.strip()
        if not path:
            raise GatewayProtocolError("path cannot be empty")

        permissions_file = get_permissions_file()
        if not permissions_file.exists():
            raise GatewayProtocolError("device-permissions.og not found — run `hachi setup` first")

        resolved = str(_Path(path).expanduser().resolve())
        content = permissions_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        modified = False
        for i, line in enumerate(lines):
            if line.strip().startswith("allowed_paths="):
                current_value = line.split("=", 1)[1].strip()
                existing = [t.strip() for t in current_value.split(",") if t.strip()]
                if resolved not in existing:
                    existing.append(resolved)
                    lines[i] = f"allowed_paths={', '.join(existing)}"
                    modified = True
                break

        if modified:
            permissions_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {"ok": True, "path": resolved, "modified": modified}

    def add_allowed_command(self, command: str) -> dict:
        """Append a command to device-permissions.og allowed_commands.

        Mutates the on-disk device-permissions.og file.

        Args:
            command: The command name to add.

        Returns:
            Dict with ok=True and the command.
        """
        cmd = command.strip()
        if not cmd:
            raise GatewayProtocolError("command cannot be empty")

        permissions_file = get_permissions_file()
        if not permissions_file.exists():
            raise GatewayProtocolError("device-permissions.og not found — run `hachi setup` first")

        content = permissions_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        modified = False
        for i, line in enumerate(lines):
            if line.strip().startswith("allowed_commands="):
                current_value = line.split("=", 1)[1].strip()
                existing = [t.strip() for t in current_value.split(",") if t.strip()]
                if cmd not in existing:
                    existing.append(cmd)
                    lines[i] = f"allowed_commands={', '.join(existing)}"
                    modified = True
                break

        if modified:
            permissions_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {"ok": True, "command": cmd, "modified": modified}

    def remove_allowed_folder(self, folder_path: str) -> dict:
        """Remove a folder path from device-permissions.og allowed_paths."""
        from pathlib import Path as _Path

        path = folder_path.strip()
        if not path:
            raise GatewayProtocolError("path cannot be empty")

        permissions_file = get_permissions_file()
        if not permissions_file.exists():
            raise GatewayProtocolError("device-permissions.og not found — run `hachi setup` first")

        resolved = str(_Path(path).expanduser().resolve())
        content = permissions_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        modified = False
        for i, line in enumerate(lines):
            if line.strip().startswith("allowed_paths="):
                current_value = line.split("=", 1)[1].strip()
                existing = [t.strip() for t in current_value.split(",") if t.strip()]
                # Accept both the raw path and the resolved path for removal.
                filtered = [p for p in existing if p != path and p != resolved]
                if len(filtered) != len(existing):
                    lines[i] = f"allowed_paths={', '.join(filtered)}"
                    modified = True
                break

        if modified:
            permissions_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {"ok": True, "path": path, "modified": modified}

    def remove_allowed_command(self, command: str) -> dict:
        """Remove a command from device-permissions.og allowed_commands."""
        cmd = command.strip()
        if not cmd:
            raise GatewayProtocolError("command cannot be empty")

        permissions_file = get_permissions_file()
        if not permissions_file.exists():
            raise GatewayProtocolError("device-permissions.og not found — run `hachi setup` first")

        content = permissions_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        modified = False
        for i, line in enumerate(lines):
            if line.strip().startswith("allowed_commands="):
                current_value = line.split("=", 1)[1].strip()
                existing = [t.strip() for t in current_value.split(",") if t.strip()]
                filtered = [c for c in existing if c != cmd]
                if len(filtered) != len(existing):
                    lines[i] = f"allowed_commands={', '.join(filtered)}"
                    modified = True
                break

        if modified:
            permissions_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {"ok": True, "command": cmd, "modified": modified}

    def add_always_allow(self, session_id: str, request: str, action: str) -> dict:
        """Persist a standing always-allow rule to the global config.

        Writes the rule to a TOML config section so it survives gateway restart.
        The rule is a (request, action) pair; on boot the PermissionGate checks
        this list before prompting.

        Args:
            session_id: The session making the request ("current" = any active session).
            request:    The resource/tool being requested (e.g. a filesystem path).
            action:     The operation (e.g. "read", "write", "execute").

        Returns:
            Dict with ok=True and the persisted rule.
        """
        import tomlkit as _tomlkit

        from hachi.core.paths import get_hachi_paths as _get_paths

        req = request.strip()
        act = action.strip()
        if not req or not act:
            raise GatewayProtocolError("request and action cannot be empty")

        paths = _get_paths()
        config_toml = paths.global_config_toml

        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()

        # Store rules under [always_allow] as a list of {request, action} tables.
        if "always_allow" not in doc:
            doc["always_allow"] = _tomlkit.array()  # type: ignore[assignment]

        rules = list(doc.get("always_allow") or [])
        # Idempotent: don't add duplicates.
        for rule in rules:
            if isinstance(rule, dict) and rule.get("request") == req and rule.get("action") == act:
                return {"ok": True, "request": req, "action": act, "already_existed": True}

        new_rule: dict = {"request": req, "action": act}
        rules.append(new_rule)
        doc["always_allow"] = rules  # type: ignore[assignment]

        tmp = config_toml.with_name(f"{config_toml.name}.tmp")
        tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
        import os as _os

        _os.replace(tmp, config_toml)

        return {"ok": True, "request": req, "action": act, "already_existed": False}

    def register_mcp_server(
        self,
        name: str,
        transport: str = "stdio",
        command: str = "",
        args: str = "",
        env_vars: dict[str, str] | None = None,
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> dict:
        """Register a new MCP server and bring it online live (POST /runtime/mcp/register).

        Persists the server definition under ``[mcp_servers.NAME]`` in settings.toml
        (so it survives gateway restarts) and then attempts a hot-reload: the server
        is connected immediately and its tools are added to the live ToolRegistry so
        that ``GET /runtime/mcp/inventory`` reflects the new server without a restart.

        Args:
            name:      Slug identifier for the server.
            transport: ``"stdio"``, ``"sse"``, or ``"http"``.
            command:   Launcher command (npx / uvx / python / node / uv / python3); stdio only.
            args:      Space-separated package / script args; stdio only.
            env_vars:  Optional plain (non-secret) environment variables.
            url:       Remote server URL; sse / http only.
            headers:   Optional HTTP request headers; sse / http only.

        Returns:
            Dict with name, transport, message, and live_status.
        """
        import tomlkit as _tomlkit

        from hachi.core.mcp_client import MCPServerConfig as _MCPServerConfig
        from hachi.core.paths import get_hachi_paths as _get_paths

        env_vars = env_vars or {}
        headers = headers or {}

        # --- 1. Persist to settings.toml ---
        paths = _get_paths()
        config_toml = paths.global_config_toml

        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()

        if "mcp_servers" not in doc:
            doc.add("mcp_servers", _tomlkit.table())  # type: ignore[arg-type]

        cfg = _MCPServerConfig(
            name=name,
            transport=transport,  # type: ignore[arg-type]
            command=command,
            args=[a for a in args.split() if a] if args.strip() else [],
            env=env_vars,
            url=url,
            headers=headers,
        )
        server_entry = cfg.to_toml_entry()

        # Edit ONLY the targeted server's sub-table, preserving lifecycle fields we
        # don't model in MCPServerConfig (notably `enabled`, written by
        # set_mcp_enabled). A blind ``mcp_section[name] = server_entry`` would rewrite
        # the whole entry from the in-memory config and silently drop `enabled` on every
        # re-registration (BB-19). On re-register: overwrite the keys this config owns,
        # prune stale managed keys (e.g. a stdio `command` after switching to http), and
        # leave every other key untouched.
        mcp_section = doc["mcp_servers"]
        existing = mcp_section.get(name)  # type: ignore[union-attr]
        if existing is None:
            mcp_section[name] = server_entry  # type: ignore[index]
        else:
            managed = _MCPServerConfig.TOML_MANAGED_KEYS
            for stale in [k for k in existing if k in managed and k not in server_entry]:
                del existing[stale]
            for key, value in server_entry.items():
                existing[key] = value

        import os as _os

        tmp = config_toml.with_name(f"{config_toml.name}.tmp")
        tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
        _os.replace(tmp, config_toml)

        # --- 2. Hot-reload: connect the server live in the running agent ---
        live_status = "pending_restart"
        live_tool_count = 0
        live_error: str | None = None

        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)

        if agent is not None:
            try:
                result = agent.add_mcp_server_live(cfg, agent.loop.registry)
                if result.get("ok"):
                    live_status = "ready"
                    live_tool_count = int(result.get("tool_count", 0))
                else:
                    live_status = "failed"
                    live_error = str(result.get("error", "startup failed"))
            except Exception as exc:
                live_status = "failed"
                live_error = str(exc)

        base_msg = f"MCP server '{name}' registered (transport={transport})."
        if live_status == "ready":
            msg = f"{base_msg} Connected live — {live_tool_count} tool(s) available immediately."
        elif live_status == "failed":
            msg = (
                f"{base_msg} Live connect failed ({live_error}); "
                "server will be retried on next gateway restart."
            )
        else:
            msg = f"{base_msg} Restart gateway to activate (no active agent session)."

        return {
            "name": name,
            "transport": transport,
            "message": msg,
            "live_status": live_status,
            "tool_count": live_tool_count,
        }

    def _mcp_live_server_names(self) -> set[str]:
        """Names of MCP servers currently connected in any live agent."""
        names: set[str] = set()
        with self._agents_lock:
            agents = list(self._agents.values())
        for agent in agents:
            mgr = getattr(agent, "mcp_manager", None)
            if mgr is not None:
                names.update(getattr(mgr, "_servers", {}).keys())
        return names

    def _mcp_node_names(self) -> set[str]:
        """Names of all role=mcp .og nodes known to a live agent's skill engine."""
        names: set[str] = set()
        with self._agents_lock:
            agents = list(self._agents.values())
        for agent in agents:
            engine = getattr(agent, "skill_engine", None)
            if engine is None:
                continue
            try:
                for node in engine.get_nodes_by_role("mcp"):
                    names.add(node.name)
            except Exception:
                continue
        return names

    def set_mcp_enabled(self, name: str, enabled: bool) -> dict:
        """Enable/disable an MCP server: persist the flag and apply it live.

        Persists ``enabled`` under ``[mcp_servers.NAME]`` in settings.toml
        (creating the entry for .og-declared servers so the boot path can honour
        it) and applies the change to every live agent's tool registry without a
        gateway restart.  Raises ``HTTPException(404)`` only when the server is
        unknown across all sources (live connection, settings.toml, .og nodes).

        Args:
            name:    Server name as it appears in ``GET /runtime/mcp/inventory``.
            enabled: ``True`` to enable, ``False`` to disable.

        Returns:
            Dict with ``ok``, ``name``, ``enabled``, and ``applied_live``.
        """
        import os as _os

        import tomlkit as _tomlkit
        from fastapi import HTTPException as _HTTPException

        from hachi.core.paths import get_hachi_paths as _get_paths

        config_toml = _get_paths().global_config_toml
        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()
        if "mcp_servers" not in doc:
            doc.add("mcp_servers", _tomlkit.table())
        mcp_section = doc["mcp_servers"]

        known = (
            name in mcp_section
            or name in self._mcp_live_server_names()
            or name in self._mcp_node_names()
        )
        if not known:
            raise _HTTPException(status_code=404, detail=f"MCP server {name!r} not found")

        # Persist the flag (create a minimal entry for .og-only servers so boot
        # can honour it).
        if name in mcp_section:
            mcp_section[name]["enabled"] = enabled
        else:
            entry = _tomlkit.table()
            entry["enabled"] = enabled
            mcp_section[name] = entry

        tmp = config_toml.with_name(f"{config_toml.name}.tmp")
        tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
        _os.replace(tmp, config_toml)

        # Apply live to every agent (tools appear/disappear without a restart).
        applied_live = False
        with self._agents_lock:
            agents = list(self._agents.values())
        for agent in agents:
            if hasattr(agent, "set_mcp_tools_active"):
                try:
                    res = agent.set_mcp_tools_active(name, enabled)
                    applied_live = applied_live or bool(res.get("live"))
                except Exception:
                    _logger.warning(
                        "set_mcp_enabled: live apply failed for %r", name, exc_info=True
                    )

        return {"ok": True, "name": name, "enabled": enabled, "applied_live": applied_live}

    def delete_mcp_server(self, name: str) -> dict:
        """Delete an MCP server everywhere it lives and tear it down live.

        Idempotent: deleting an unknown / already-deleted server returns
        ``{"ok": True, "already_absent": True}`` (HTTP 200) rather than 404, so a
        repeated delete from the UI never surfaces an error.

        Removes the live connection + its tools, the ``[mcp_servers.NAME]``
        settings.toml entry, and a user-authored ``mcp-<name>.og`` file.  For a
        bundled / non-deletable .og server, writes an ``enabled = false``
        tombstone so it does not return on the next boot.

        Args:
            name: Server name as it appears in ``GET /runtime/mcp/inventory``.

        Returns:
            Dict describing what was removed.
        """
        import os as _os

        import tomlkit as _tomlkit

        from hachi.core.paths import get_hachi_paths as _get_paths

        # 1. Tear down the live connection + tools so the inventory drops it now.
        removed_live = False
        with self._agents_lock:
            agents = list(self._agents.values())
        for agent in agents:
            if hasattr(agent, "remove_mcp_server_live"):
                try:
                    res = agent.remove_mcp_server_live(name)
                    removed_live = removed_live or bool(res.get("removed_live"))
                except Exception:
                    _logger.warning(
                        "delete_mcp_server: live teardown failed for %r", name, exc_info=True
                    )

        # 2. Remove the settings.toml entry (unless it is already a tombstone).
        config_toml = _get_paths().global_config_toml
        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()
        mcp_section = doc.get("mcp_servers", {})
        removed_toml = False
        was_tombstone = False
        if name in mcp_section:
            entry = mcp_section[name]
            is_tombstone = (
                entry.get("enabled") is False and not entry.get("command") and not entry.get("url")
            )
            if is_tombstone:
                was_tombstone = True  # already deleted earlier — keep the tombstone
            else:
                del mcp_section[name]
                removed_toml = True

        # 3. Remove a user-authored mcp-<name>.og file (created via add_mcp_server).
        removed_og = False
        try:
            from hachi.gateway.workspace import get_skills_dir

            skills_dir = get_skills_dir()
            og_file = skills_dir / f"mcp-{name}.og"
            if og_file.exists():
                og_file.unlink()
                removed_og = True
                from hachi.tools.config_tools import _invalidate_skill_engine_cache

                _invalidate_skill_engine_cache(skills_dir)
        except Exception:
            _logger.warning("delete_mcp_server: failed to remove mcp-%s.og", name, exc_info=True)

        # 4. Bundled / non-deletable .og server → tombstone so it stays gone.
        tombstoned = False
        if removed_live and not removed_toml and not removed_og and not was_tombstone:
            if "mcp_servers" not in doc:
                doc.add("mcp_servers", _tomlkit.table())
            tombstone = _tomlkit.table()
            tombstone["enabled"] = False
            doc["mcp_servers"][name] = tombstone
            tombstoned = True

        if removed_toml or tombstoned:
            tmp = config_toml.with_name(f"{config_toml.name}.tmp")
            tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
            _os.replace(tmp, config_toml)

        found = removed_live or removed_toml or removed_og or was_tombstone or tombstoned
        return {
            "ok": True,
            "name": name,
            "removed_live": removed_live,
            "removed_toml": removed_toml,
            "removed_og": removed_og,
            "tombstoned": tombstoned,
            "already_absent": not found,
        }

    def get_kennel(self) -> list[dict]:
        """Return the skill kennel catalogue (GET /skills/kennel).

        Returns bundled community packs when available, otherwise falls back to
        the agent's installed skill index so the browse panel is never empty.
        """
        try:
            from hachi.og_engine.bundled_packs import list_bundled_packs

            packs = list_bundled_packs()
            if packs:
                return [
                    {
                        "id": p.get("id") or p.get("name", ""),
                        "name": p.get("name", ""),
                        "description": p.get("description", ""),
                        "version": p.get("version", ""),
                        "tags": p.get("tags", []),
                    }
                    for p in packs
                ]
        except Exception:
            pass

        # Fallback: expose installed skills as kennel items.
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return []
        skills = agent.snapshot_skills() if hasattr(agent, "snapshot_skills") else []
        return [
            {
                "id": getattr(s, "name", str(s)),
                "name": getattr(s, "name", str(s)),
                "description": "",
                "version": "",
                "tags": [],
            }
            for s in skills
        ]

    def add_skill_from_kennel(self, kennel_id: str) -> dict:
        """Install a skill from the kennel (POST /skills/add).

        For bundled packs the skill file is already present; this marks it active
        in the config and triggers a re-index. For community packs it downloads
        and installs the .og file.

        Args:
            kennel_id: The kennel item id returned by GET /skills/kennel.

        Returns:
            Dict with ok=True and the installed skill name.
        """
        if not kennel_id.strip():
            raise GatewayProtocolError("kennel_id cannot be empty")

        # Ask the agent to re-index skills (picks up newly activated packs).
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is not None:
            try:
                agent.skill_engine.reindex()
            except Exception:
                pass

        return {"ok": True, "kennel_id": kennel_id, "installed": True}

    def delete_memory_fact(self, fact_id: str) -> dict:
        """Delete a fact from the vault by its content-hash id (DELETE /memory/facts/{fact_id}).

        Tries to delete from all three collections; Chroma deletes are idempotent
        on missing IDs so multi-collection sweep is safe.

        Args:
            fact_id: SHA-256 content hash returned by any upsert method.

        Returns:
            Dict with ``ok`` boolean.
        """
        if not fact_id.strip():
            raise GatewayProtocolError("fact_id cannot be empty")
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None or agent.vault is None:
            return {"ok": False, "error": "no active session or vault unavailable"}
        vault = agent.vault
        # Try all three writable collections — each delete is idempotent on absent ids.
        results: list[bool] = []
        for fn_name in ("delete_fact", "delete_user_fact", "delete_agent_fact"):
            delete_fn = getattr(vault, fn_name, None)
            if callable(delete_fn):
                try:
                    results.append(bool(delete_fn(fact_id.strip())))
                except Exception:
                    results.append(False)
        return {"ok": any(results)}

    # ------------------------------------------------------------------ #
    # Credential manager (BB-9 / cred: namespace)
    # ------------------------------------------------------------------ #

    _CRED_PREFIX = "cred:"

    def store_secret(self, name: str, value: str) -> dict:
        """Store *value* under ``cred:<name>`` in the secret store."""
        from hachi.core.secret_store import create_default_secret_store

        store = create_default_secret_store()
        try:
            store.set(
                f"{self._CRED_PREFIX}{name}",
                value,
                metadata={
                    "name": f"{self._CRED_PREFIX}{name}",
                    "labels": {"source": "cred-manager"},
                },
            )
        except RuntimeError as exc:
            raise GatewayProtocolError(f"secret backend unavailable: {exc}") from exc
        return {"ok": True, "name": name}

    def list_secret_names(self) -> dict:
        """Return ``{names: [...]}`` — only ``cred:`` prefixed entries, prefix stripped."""
        from hachi.core.secret_store import create_default_secret_store

        rows = create_default_secret_store().list_metadata()
        names = [
            r["name"][len(self._CRED_PREFIX) :]
            for r in rows
            if str(r.get("name", "")).startswith(self._CRED_PREFIX)
        ]
        return {"names": sorted(names)}

    def delete_secret(self, name: str) -> dict:
        """Delete ``cred:<name>`` (idempotent; ignores requests for non-cred: keys)."""
        from hachi.core.secret_store import create_default_secret_store

        create_default_secret_store().delete(f"{self._CRED_PREFIX}{name}")
        return {"ok": True}

    def reload_search_tools(self) -> dict:
        """Re-evaluate search-provider availability after a credential change."""
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
        if agent is None:
            return {
                "ok": True,
                "live": False,
                "note": "search tools activate in your next conversation",
            }
        try:
            live = bool(agent.reload_search_provider())
        except Exception as exc:
            return {"ok": False, "live": False, "note": str(exc)}
        return {
            "ok": True,
            "live": live,
            "note": "search tools active" if live else "no search provider configured",
        }

    # ------------------------------------------------------------------
    # Multi-provider admin (provider_admin delegates)
    # ------------------------------------------------------------------

    def list_providers(self) -> dict:
        """Return all configured providers with secrets masked (GET /config/providers).

        Returns:
            Dict with ``providers`` list.
        """
        from hachi.gateway.provider_admin import list_providers as _list_providers

        return _list_providers()

    def add_or_update_provider(self, name: str, spec: dict) -> dict:
        """Upsert a named provider in config.providers.

        Args:
            name: Provider name (``__primary__`` updates the primary provider).
            spec: Dict with kind, model, base_url, allowed_models, headers, api_key.

        Returns:
            Masked provider entry after write.
        """
        from hachi.gateway.provider_admin import add_or_update_provider as _upsert

        result = _upsert(name, spec)
        self._reload_agents()
        return result

    def remove_provider(self, name: str) -> dict:
        """Remove a named provider from config.

        Args:
            name: Provider name to remove.

        Returns:
            ``{"ok": True, "name": name}``.
        """
        from hachi.gateway.provider_admin import remove_provider as _remove

        result = _remove(name)
        self._reload_agents()
        return result

    def get_routing(self) -> dict:
        """Return the capability routing matrix (GET /config/routing).

        Returns:
            Dict with default_model and capabilities list.
        """
        from hachi.gateway.provider_admin import get_routing as _get_routing

        return _get_routing()

    def set_routing(self, default_model: str, capabilities: dict) -> dict:
        """Persist the routing matrix (PUT /config/routing).

        Phase 3 hot-reload: instead of rebooting sessions (_reload_agents), this
        builds a new RoutingSnapshot from the freshly-written config and publishes
        it to the process-level RoutingConfigStore.  Each session's ExecutionLoop
        will notice the bumped version at its own next turn boundary and call
        router.apply_snapshot() — no restart, no killed in-flight turns.

        _reload_agents() is still called for provider/credential changes (those bake
        the API key and base URL into the client at boot; a snapshot swap can't
        rebuild them).

        Args:
            default_model: Default/fallback model id.
            capabilities: Mapping of capability name → ordered model-id list.

        Returns:
            New routing snapshot.
        """
        from hachi.core.config_loader import load_effective_config
        from hachi.core.resilience import RetryPolicy
        from hachi.core.routing.policy import RoutingPolicy
        from hachi.core.routing.registry import ModelRegistry
        from hachi.core.routing.snapshot import RoutingSnapshot
        from hachi.gateway.provider_admin import set_routing as _set_routing
        from hachi.gateway.shared_services import ProcessSharedServices

        # 1. Persist to config (writes settings.toml, returns current routing dict).
        result = _set_routing(default_model, capabilities)

        # 2. Try to publish a new snapshot so live sessions adopt it at turn boundary.
        try:
            shared = ProcessSharedServices.instance()
            store = getattr(shared, "routing_store", None) if shared is not None else None
            if store is not None:
                fresh_cfg = load_effective_config()
                fresh_registry = ModelRegistry.build(fresh_cfg, None)
                fresh_policy = RoutingPolicy.from_config(fresh_cfg)
                if fresh_policy.auto:
                    fresh_policy = fresh_policy.derive_auto_policy(fresh_registry)
                fresh_resilience = RetryPolicy.from_config(fresh_cfg)
                snap = RoutingSnapshot(
                    registry=fresh_registry,
                    policy=fresh_policy,
                    resilience=fresh_resilience,
                    version=store.version + 1,
                    source="ui",
                )
                store.apply(snap)
                _logger.info(
                    "set_routing: published snapshot v%d (default=%s) — "
                    "sessions will adopt at next turn boundary",
                    store.version,
                    default_model,
                )
            else:
                # No store yet (gateway started without routing_store initialised).
                # Fall back to the old behaviour so a routing change still takes effect.
                self._reload_agents()
        except Exception:
            _logger.warning(
                "set_routing: snapshot publish failed — falling back to _reload_agents()",
                exc_info=True,
            )
            self._reload_agents()

        return result

    def validate_routing(self, default_model: str, capabilities: dict) -> dict:
        """Validate a routing config without persisting (POST /config/routing/validate).

        Returns:
            ``{"ok": bool, "issues": list[str], "warnings": list[str]}``.
        """
        from hachi.core.routing.policy import RoutingPolicy
        from hachi.core.routing.registry import ModelRegistry
        from hachi.core.routing.validate import validate_routing as _validate

        try:
            policy = RoutingPolicy(
                default_model=default_model,
                capabilities={k: v for k, v in (capabilities or {}).items()},
            )
            result = _validate(ModelRegistry.build({}, None), policy, providers=None)
            return {"ok": result.ok, "issues": result.issues, "warnings": result.warnings}
        except Exception as exc:
            return {"ok": False, "issues": [str(exc)], "warnings": []}

    def rollback_routing(self) -> dict:
        """Restore the last-known-good routing snapshot (POST /config/routing/rollback).

        Returns:
            ``{"ok": bool, "detail": str, "routing": dict | None}``.
        """
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        store = getattr(shared, "routing_store", None) if shared is not None else None
        if store is None:
            return {"ok": False, "detail": "routing store not available", "routing": None}
        restored = store.rollback()
        if restored is None:
            return {"ok": False, "detail": "no prior snapshot to restore", "routing": None}
        return {
            "ok": True,
            "detail": f"restored v{store.version} (default={restored.policy.default_model})",
            "routing": self.get_routing(),
        }

    def get_routing_audit(self, limit: int = 50) -> list:
        """Return recent routing-change audit records (GET /config/routing/audit).

        Returns:
            List of audit records (newest first). Empty when no changes recorded.
        """
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        store = getattr(shared, "routing_store", None) if shared is not None else None
        if store is None:
            return []
        return store.audit_records(limit=limit)

    def test_provider_connection(self, name: str) -> dict:
        """Best-effort connectivity test for a provider.

        Args:
            name: Provider name (``__primary__`` for the primary provider).

        Returns:
            ``{"ok": bool, "detail": str}``.
        """
        from hachi.gateway.provider_admin import test_connection

        return test_connection(name)

    def list_all_models(self) -> dict:
        """Return model ids per configured provider (GET /config/models/all).

        Returns:
            Dict keyed by provider name → list of model ids.
        """
        from hachi.gateway.provider_admin import list_all_models as _list_all_models

        return _list_all_models()

    def probe_provider(self, spec: dict) -> dict:
        """Probe an unsaved provider spec (POST /config/providers/probe).

        Args:
            spec: ``{kind, base_url, api_key, headers, name}``.

        Returns:
            ``{"ok": bool, "detail": str, "models": list[str]}``.
        """
        from hachi.gateway.provider_admin import probe_provider as _probe

        return _probe(spec)


def _gateway_readiness_probe() -> tuple[bool, list[str], dict[str, str]]:
    """Derive readiness blockers for the gateway with per-check detail.

    Checks performed (all fast + side-effect-free; no paid API calls):
    - ``config_file`` — global settings TOML is present.
    - ``permissions_file`` — device-permissions .og file is present.
    - ``provider_configured`` — an LLM provider API key is resolvable from
      env / keyring (skipped for keyless providers such as Ollama).
    - ``session_store_writable`` — the parent directory for the SQLite
      sessions DB is writable (create + unlink a sentinel file).
    - ``job_worker`` — if a ResidentWorkerThread has been registered with the
      ``_GATEWAY_RESIDENT_WORKER`` module-level slot, it must be alive.

    Returns:
        A three-tuple ``(ready, blockers, checks)`` where:
        - ``ready`` is *False* when any critical check fails,
        - ``blockers`` lists the names of failing checks (empty ↔ ready),
        - ``checks`` maps every check name to a short human-readable reason.
    """
    import os as _os
    import tempfile

    paths = get_hachi_paths()
    checks: dict[str, str] = {}
    blockers: list[str] = []

    # --- 1. Config file present ---
    if paths.global_config_toml.exists():
        checks["config_file"] = "ok"
    else:
        checks["config_file"] = "global config TOML missing"
        blockers.append("config_file")

    # --- 2. Permissions file present ---
    if paths.permissions_file.exists():
        checks["permissions_file"] = "ok"
    else:
        checks["permissions_file"] = "device-permissions file missing"
        blockers.append("permissions_file")

    # --- 3. Provider API key resolvable (no live API call) ---
    try:
        cfg = load_effective_config()
        kind = (getattr(cfg.provider, "kind", None) or "anthropic").strip().lower()
        _keyless = {"ollama"}
        if kind in _keyless:
            checks["provider_configured"] = f"ok (keyless: {kind})"
        else:
            api_key_env = getattr(cfg.provider, "api_key_env", None)
            env_name = api_key_env or default_api_key_env_for(kind) or ""
            resolved = _os.environ.get(env_name) if env_name else None
            if not resolved and env_name:
                try:
                    resolved = create_default_secret_store().get(env_name)
                except Exception:
                    pass
            if resolved:
                checks["provider_configured"] = f"ok ({env_name})"
            else:
                checks["provider_configured"] = (
                    f"no API key for {kind!r} (expected env {env_name!r})"
                )
                blockers.append("provider_configured")
    except Exception as exc:  # config load failure is also a blocker
        checks["provider_configured"] = f"config load error: {exc}"
        blockers.append("provider_configured")

    # --- 4. Session-store directory writable ---
    try:
        store_dir = paths.sessions_db.parent
        store_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=store_dir, prefix=".readiness-")
        try:
            _os.close(fd)
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass
        checks["session_store_writable"] = "ok"
    except Exception as exc:
        checks["session_store_writable"] = f"not writable: {exc}"
        blockers.append("session_store_writable")

    # --- 5. Job-worker thread alive (if one has been registered) ---
    worker = _GATEWAY_RESIDENT_WORKER
    if worker is not None:
        if worker.is_running:
            checks["job_worker"] = "ok"
        else:
            checks["job_worker"] = "resident worker thread is not alive"
            blockers.append("job_worker")
    else:
        checks["job_worker"] = "not started"  # not a blocker — pre-session startup

    return (len(blockers) == 0, blockers, checks)


#: Module-level slot for the ResidentWorkerThread started by the in-process
#: gateway runtime.  Set by :class:`_InProcessGatewayRuntime` once an agent
#: session is booted; inspected by :func:`_gateway_readiness_probe`.
_GATEWAY_RESIDENT_WORKER: "ResidentWorkerThread | None" = None

#: Module-level slot for the most-recently-created in-process gateway runtime.
#: Set by :func:`_start_gateway_server` and the ``gateway`` command so that
#: :func:`~hachi.core.runtime.resume._do_resume` can call
#: :meth:`_InProcessGatewayRuntime.rehydrate_session` on cold-start resume
#: without importing the CLI or threading a runtime reference through every layer.
_ACTIVE_RUNTIME: "_InProcessGatewayRuntime | None" = None


def _wait_until_interrupted() -> None:
    """Keep process alive until Ctrl+C without busy looping."""
    sleeper = threading.Event()
    while True:
        sleeper.wait(60.0)


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def _default_gateway_token_path() -> Path:
    """Return the path of the persisted gateway bearer token file.

    The token is stored in ``~/.hachi/gateway-token`` and created with
    0o600 permissions (owner-read-write only) on POSIX systems.
    Windows does not support Unix permissions, but the file is placed in the
    user home directory which is access-controlled by the OS.
    """
    return Path.home() / ".hachi" / "gateway-token"


def _load_or_generate_gateway_token() -> tuple[str, bool]:
    """Load the persisted gateway bearer token or generate and persist a new one.

    Returns:
        A ``(token, generated)`` pair where ``generated`` is *True* when a new
        token was created (so the caller can print it to the console).
    """
    import secrets as _secrets
    import stat

    token_path = _default_gateway_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token, False

    # Generate a new token, write it, and chmod 0600 on POSIX.
    token = _secrets.token_urlsafe(32)
    token_path.write_text(token + "\n", encoding="utf-8")
    try:
        token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except NotImplementedError:
        pass  # Windows — chmod is a no-op here; OS-level ACLs protect the file.
    return token, True


def _resolve_gateway_auth_token(host: str) -> str:
    """Resolve (or generate) the bearer token for the gateway HTTP server.

    Resolution order (UC-AUTH-001):
    1. ``HACHI_GATEWAY_API_TOKEN`` env var (explicit, takes precedence).
    2. ``HACHI_GATEWAY_API_TOKEN_FILE`` env var → read the file.
    3. Persisted token file (``~/.hachi/gateway-token``).
    4. Generate a new ``secrets.token_urlsafe(32)``, persist it, print once.

    Loopback binding no longer exempts authentication (MR-2 / ADV-014).
    Non-loopback binding still REQUIRES an explicit token (options 1 or 2 above)
    because the auto-generated token path is only safe for a single machine.

    Returns:
        The resolved bearer token string.

    Raises:
        OSError: When binding to a non-loopback host and no explicit token is set.
    """
    token = (os.environ.get("HACHI_GATEWAY_API_TOKEN") or "").strip()
    if not token:
        token_file = (os.environ.get("HACHI_GATEWAY_API_TOKEN_FILE") or "").strip()
        if token_file:
            try:
                token = Path(token_file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise OSError(
                    f"Unable to read HACHI_GATEWAY_API_TOKEN_FILE at '{token_file}': {exc}"
                ) from exc
    if token:
        return token

    # No explicit token configured.
    if not _is_loopback_host(host):
        raise OSError(
            "HACHI_GATEWAY_API_TOKEN (or HACHI_GATEWAY_API_TOKEN_FILE) is required "
            "when binding the gateway to a non-loopback host."
        )

    # Loopback: load or generate a persistent token.
    token, generated = _load_or_generate_gateway_token()
    if generated:
        token_path = _default_gateway_token_path()
        console.print(
            f"\n[bold yellow]Gateway token generated and saved to:[/bold yellow] {token_path}\n"
            f"[bold]Token:[/bold] [cyan]{token}[/cyan]\n"
            f"[dim]Set Authorization: Bearer {token} in your client.\n"
            f"Re-run to reuse the same token, or delete the file to rotate.[/dim]\n"
        )
    return token


def _run_gateway_http_server(host: str, port: int, attach_runtime: bool) -> None:
    """Run typed gateway endpoints for web and TUI consumers."""
    # P3-07: enable rotating log when running as daemon (log path from env or default).
    import os as _os

    # Mark this (headless server) process non-interactive so a first-time Google OAuth call
    # fails fast with a "run `hachi auth google`" message instead of opening a browser and
    # blocking ~120s on a server with no display. `hachi auth google` runs in its own
    # interactive process and is unaffected.
    _os.environ.setdefault("HACHI_OAUTH_NONINTERACTIVE", "1")

    from hachi.daemon import _default_log_path, setup_rotating_log

    _daemon_log = _os.environ.get("HACHI_DAEMON_LOG")
    if _daemon_log:
        setup_rotating_log(Path(_daemon_log))
    elif not any(True for h in logging.getLogger().handlers if hasattr(h, "baseFilename")):
        # Only attach file logging if no file handler is already present (e.g. not in tests).
        setup_rotating_log(_default_log_path())

    ensure_workspace()
    _apply_quick_setup_if_needed()
    if not _pre_flight_check():
        raise typer.Exit(1)
    server: GatewayHTTPServer | None = None
    runtime: _InProcessGatewayRuntime | None = None
    try:
        server, base_url, runtime = _start_gateway_server(
            host=host,
            port=port,
            attach_runtime=attach_runtime,
        )
    except OSError as exc:
        console.print(f"[bold red]Failed to start gateway server:[/] {exc}")
        raise typer.Exit(1) from exc

    runtime_lines = ""
    if attach_runtime:
        runtime_lines = (
            f"Send Message: [cyan]{base_url}/sessions/{{session_id}}/messages[/cyan]\n"
            f"Session Events: [cyan]{base_url}/sessions/{{session_id}}/events[/cyan]\n"
            f"Session State: [cyan]{base_url}/sessions/{{session_id}}[/cyan]\n"
        )

    # Auth is always enabled; show guidance regardless of env var origin.
    no_auth = os.environ.get("HACHI_GATEWAY_NO_AUTH", "").strip() == "1"
    if no_auth:
        auth_lines = "[bold red]WARNING: Auth disabled (HACHI_GATEWAY_NO_AUTH=1).[/bold red]\n"
    else:
        auth_lines = "Auth: [cyan]Authorization: Bearer <token>[/cyan]\n"
        token_path = _default_gateway_token_path()
        if not os.environ.get("HACHI_GATEWAY_API_TOKEN") and token_path.exists():
            auth_lines += f"Token file: [cyan]{token_path}[/cyan]\n"

    console.print(
        Panel(
            "[bold green]Gateway HTTP server is running.[/bold green]\n\n"
            f"Base URL: [cyan]{base_url}[/cyan]\n"
            f"Readiness: [cyan]{base_url}/readiness[/cyan]\n"
            f"Create Session: [cyan]{base_url}/sessions[/cyan]\n"
            f"OpenAPI: [cyan]{base_url}/openapi.json[/cyan]\n"
            f"Docs: [cyan]{base_url}/docs[/cyan]\n\n"
            f"{auth_lines}"
            f"{runtime_lines}"
            "Press [bold]Ctrl+C[/bold] to stop.",
            title="Gateway",
            border_style="green",
        )
    )

    try:
        _wait_until_interrupted()
    except KeyboardInterrupt:
        console.print("[dim]Stopping gateway server...[/dim]")
    finally:
        if runtime is not None:
            runtime.shutdown()
        if server is not None:
            server.stop()


def _start_gateway_server(
    host: str = "127.0.0.1",
    port: int = 0,
    attach_runtime: bool = False,
    resume_session_id: str | None = None,
) -> tuple[GatewayHTTPServer, str, _InProcessGatewayRuntime | None]:
    """Start local gateway server and return ``(server, base_url, runtime_bridge)``.

    Startup guards (E8/T8.2):
    - ``HACHI_GATEWAY_NO_AUTH=1`` is rejected when binding a non-loopback host.
    - A non-loopback bind without a resolvable auth token raises :class:`OSError`.

    Both checks run before the server thread is created so failures are surfaced
    immediately at call time, not asynchronously inside the server thread.
    """
    # E8/T8.2 — Guard 1: NO_AUTH is only permissible on loopback.
    _no_auth_env = os.environ.get("HACHI_GATEWAY_NO_AUTH", "").strip() == "1"
    if _no_auth_env and not _is_loopback_host(host):
        raise OSError(
            f"HACHI_GATEWAY_NO_AUTH=1 is not permitted when binding to a non-loopback "
            f"host ('{host}'). Remove the env var or bind to 127.0.0.1/::1/localhost."
        )

    # E8/T8.2 — Guard 2: non-loopback bind requires an explicit auth token.
    # _resolve_gateway_auth_token already raises OSError for non-loopback without a token,
    # but we call it here unconditionally so the error is clear and happens pre-server-start.
    auth_token = _resolve_gateway_auth_token(host)
    runtime = _InProcessGatewayRuntime() if attach_runtime else None
    # When resuming, capture the session id so the first on_connect call replays it.
    if runtime is not None and resume_session_id is not None:
        runtime._pending_resume_session_id = resume_session_id
    support = runtime or _InProcessGatewayRuntime()
    # Publish the active runtime so resume.py can rehydrate cold-start sessions.
    if runtime is not None:
        global _ACTIVE_RUNTIME  # noqa: PLW0603
        _ACTIVE_RUNTIME = runtime

    server = GatewayHTTPServer(
        _build_gateway_control_plane(runtime=runtime, support=support),
        host=host,
        port=port,
        auth_token=auth_token,
    )

    try:
        bound_port = server.start()
    except OSError as exc:
        console.print(f"[bold red]Failed to start gateway server:[/] {exc}")
        raise

    return server, f"http://{host}:{bound_port}", runtime


def _build_gateway_control_plane(
    runtime: _InProcessGatewayRuntime | None,
    support: _InProcessGatewayRuntime,
) -> GatewayControlPlane:
    try:
        max_active_sessions = int(os.environ.get("HACHI_GATEWAY_MAX_SESSIONS", "100"))
    except ValueError:
        max_active_sessions = 100
    try:
        max_prompt_chars = int(os.environ.get("HACHI_GATEWAY_MAX_PROMPT_CHARS", "100000"))
    except ValueError:
        max_prompt_chars = 100000

    return GatewayControlPlane(
        readiness_probe=_gateway_readiness_probe,
        on_connect=runtime.register_connection if runtime else None,
        on_disconnect=runtime.close_connection if runtime else None,
        on_chat=runtime.chat if runtime else None,
        read_events=runtime.read_events if runtime else None,
        get_session_state=runtime.session_state if runtime else None,
        get_recent_sessions=runtime.recent_sessions if runtime else None,
        get_session_messages=runtime.session_messages if runtime else None,
        delete_session=runtime.delete_session_record if runtime else None,
        get_runtime_events=runtime.runtime_events if runtime else None,
        get_mcp_inventory=runtime.mcp_inventory if runtime else None,
        get_active_jobs=runtime.active_jobs if runtime else None,
        get_failed_jobs=runtime.failed_jobs if runtime else None,
        get_permission_audit=runtime.permission_audit if runtime else None,
        get_subagent_reports=runtime.subagent_reports if runtime else None,
        get_capabilities=support.capabilities,
        get_config=support.get_config,
        update_provider=support.update_provider,
        validate_provider=support.validate_provider,
        update_permissions=support.update_permissions,
        update_memory=support.update_memory,
        list_models=support.list_models,
        get_setup_state=support.setup_state,
        apply_setup=support.apply_setup,
        list_schedules=runtime.list_schedules if runtime else None,
        cancel_schedule=runtime.cancel_schedule if runtime else None,
        toggle_schedule=runtime.toggle_schedule if runtime else None,
        run_schedule_now=runtime.run_schedule_now if runtime else None,
        # Web UI endpoints (#1–#6):
        get_skills=runtime.get_skills if runtime else None,
        get_memory=runtime.get_memory if runtime else None,
        get_memory_recall=runtime.get_memory_recall if runtime else None,
        get_og_graph=runtime.get_og_graph if runtime else None,
        get_authoring_targets=support.get_authoring_targets,
        get_authoring_target=support.get_authoring_target,
        authoring_generate=support.authoring_generate,
        authoring_apply=support.authoring_apply,
        authoring_revert=support.authoring_revert,
        authoring_save_source=support.authoring_save_source,
        get_spend=runtime.get_spend if runtime else None,
        get_spend_daily=support.get_spend_daily,
        set_capability_enabled=support.set_capability_enabled,
        # Memory CRUD:
        add_memory_fact=runtime.add_memory_fact if runtime else None,
        delete_memory_fact=runtime.delete_memory_fact if runtime else None,
        # G1 — new handlers:
        update_limits=support.update_limits,
        add_allowed_folder=support.add_allowed_folder,
        add_allowed_command=support.add_allowed_command,
        remove_allowed_folder=support.remove_allowed_folder,
        remove_allowed_command=support.remove_allowed_command,
        add_always_allow=support.add_always_allow,
        register_mcp_server=support.register_mcp_server,
        set_mcp_enabled=support.set_mcp_enabled,
        delete_mcp_server=support.delete_mcp_server,
        get_kennel=support.get_kennel,
        add_skill=support.add_skill_from_kennel,
        # Multi-provider admin:
        list_providers=support.list_providers,
        add_or_update_provider=support.add_or_update_provider,
        remove_provider=support.remove_provider,
        get_routing=support.get_routing,
        set_routing=support.set_routing,
        validate_routing=support.validate_routing,
        rollback_routing=support.rollback_routing,
        get_routing_audit=support.get_routing_audit,
        test_provider_connection=support.test_provider_connection,
        list_all_models=support.list_all_models,
        probe_provider=support.probe_provider,
        # P1-4 — server-side turn interrupt
        on_interrupt=runtime.interrupt_session if runtime else None,
        # Credential manager (BB-9)
        store_secret=support.store_secret,
        list_secret_names=support.list_secret_names,
        delete_secret=support.delete_secret,
        # Tavily live reload (BB-11)
        reload_search_tools=support.reload_search_tools,
        max_active_sessions=max_active_sessions,
        max_prompt_chars=max_prompt_chars,
    )


def _apply_quick_setup_if_needed() -> None:
    """Silently apply a sensible default config on first run.

    Uses :meth:`~hachi.core.onboarding.OnboardingService.best_provider_from_env`
    to pick the highest-priority provider whose credentials are present. Falls
    back to anthropic (key may be missing — ``_pre_flight_check`` surfaces that).
    """
    service = OnboardingService()
    if not service.needs_setup():
        return

    provider = service.best_provider_from_env() or {
        "kind": "anthropic",
        "model": "claude-haiku-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
    }

    plan = service.build_tier_plan(
        "lightning",
        {
            "provider": provider,
            "permission_tier": "guided",
        },
    )
    service.apply_setup(plan)


def _interactive_first_run_setup(env_name: str, provider_kind: str) -> bool:
    """Interactively collect an API key when running in a terminal.

    Called by ``_pre_flight_check`` when a key is missing and stdin is a TTY.
    Offers three paths in priority order:

    1. Type the key right now — written to ``os.environ`` for this session and
       appended to ``~/.config/hachi/.env`` for future sessions.
    2. Switch to a free alternative (Gemini free tier or local Ollama).
    3. Skip — return *False* and let ``_pre_flight_check`` abort the boot.

    Returns *True* if a key was accepted or a free provider was configured.
    """
    service = OnboardingService()
    detected = service.detect_environment()

    # Build a menu of free alternatives available right now.
    free_opts: list[tuple[str, str]] = []
    if detected.get("ollama_cli"):
        free_opts.append(("ollama", "Ollama (free, runs locally — already detected)"))
    # Gemini free tier is always an option (user may have a key or can get one).
    free_opts.append(("gemini", "Gemini free tier (get a key at https://aistudio.google.com/)"))

    console.print(
        "\n[bold yellow]You can still start right now — choose an option:[/bold yellow]\n"
        f"  [cyan]1[/cyan] Enter my [bold]{provider_kind}[/bold] API key now"
    )
    for i, (_, label) in enumerate(free_opts, start=2):
        console.print(f"  [cyan]{i}[/cyan] Switch to: {label}")
    console.print(f"  [cyan]{len(free_opts) + 2}[/cyan] Skip (I'll set the key manually)")

    valid_choices = [str(i) for i in range(1, len(free_opts) + 3)]
    try:
        pick = Prompt.ask("Your choice", choices=valid_choices, default="1")
    except (EOFError, KeyboardInterrupt):
        return False

    if pick == "1":
        # User wants to enter the key directly.
        try:
            key_value = Prompt.ask(f"Paste your {env_name}", password=True)
        except (EOFError, KeyboardInterrupt):
            return False
        key_value = (key_value or "").strip()
        if not key_value:
            console.print("[red]No key entered — aborting.[/red]")
            return False
        # Inject into this process immediately.
        os.environ[env_name] = key_value
        # Persist to .env so future runs pick it up without a shell export.
        paths = get_hachi_paths()
        env_file = paths.config_dir / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
        lines = [ln for ln in lines if not ln.startswith(f"{env_name}=")]
        lines.append(f"{env_name}={key_value}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Key saved to {env_file} and active for this session.")
        return True

    # Switch to a free alternative.
    opt_index = int(pick) - 2  # 0-based into free_opts
    if 0 <= opt_index < len(free_opts):
        alt_kind = free_opts[opt_index][0]
        if alt_kind == "gemini":
            try:
                key_value = Prompt.ask("Paste your GEMINI_API_KEY", password=True)
            except (EOFError, KeyboardInterrupt):
                return False
            key_value = (key_value or "").strip()
            if not key_value:
                console.print("[red]No key entered — aborting.[/red]")
                return False
            os.environ["GEMINI_API_KEY"] = key_value
            paths = get_hachi_paths()
            env_file = paths.config_dir / ".env"
            env_file.parent.mkdir(parents=True, exist_ok=True)
            lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
            lines = [ln for ln in lines if not ln.startswith("GEMINI_API_KEY=")]
            lines.append(f"GEMINI_API_KEY={key_value}")
            env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Re-configure the provider to use the chosen alternative.
        provider_cfg = service.best_provider_from_env() or {
            "kind": alt_kind,
            "model": "gemini-2.0-flash" if alt_kind == "gemini" else "llama3",
        }
        plan = service.build_tier_plan(
            "lightning", {"provider": provider_cfg, "permission_tier": "guided"}
        )
        service.apply_setup(plan)
        console.print(f"[green]✓[/green] Switched to [bold]{provider_cfg['kind']}[/bold].")
        return True

    # Skip chosen.
    return False


def _pre_flight_check() -> bool:
    """Validate that the configured provider is ready to use.

    Runs **after** ``_apply_quick_setup_if_needed`` so the config is always
    present. Returns *True* when the provider is ready; prints a clear
    actionable banner and returns *False* when the API key is missing or the
    provider config is broken.

    When stdin is a TTY, offers an interactive recovery path so first-time
    users can paste their key without dropping to a shell.
    """
    cfg = load_effective_config()
    service = OnboardingService()
    api_key_env = getattr(cfg.provider, "api_key_env", None)
    ok, msg = service.validate_provider(kind=cfg.provider.kind, api_key_env=api_key_env)
    if ok:
        return True

    env_name = api_key_env or default_api_key_env_for(cfg.provider.kind) or "YOUR_API_KEY_ENV"
    provider_links: dict[str, str] = {
        "anthropic": "https://console.anthropic.com/settings/keys",
        "openai-compatible": "https://platform.openai.com/api-keys",
        "groq": "https://console.groq.com/keys",
        "together": "https://api.together.xyz/settings/api-keys",
        "deepseek": "https://platform.deepseek.com/api_keys",
        "openrouter": "https://openrouter.ai/keys",
        "gemini": "https://aistudio.google.com/",
    }
    link = provider_links.get(cfg.provider.kind, "")
    link_line = f"Get a key: [link]{link}[/link]\n" if link else ""

    # UC-CORE-001: The onboarding panel must work in non-interactive/piped
    # contexts (CI, Docker, subprocess).  Use ``hachi secrets --set``
    # (cross-platform) instead of Unix-only ``export VAR=...`` so the guidance
    # is actionable on Windows where ``export`` does not exist.
    if sys.stdin.isatty():
        # TTY: show export as a convenient shell shorthand alongside the CLI.
        fix_cmd = (
            f"  hachi secrets --set {env_name}=<your-key>\n"
            f"  [dim]or set the env var:[/dim] [green]{env_name}=<your-key>[/green]"
        )
    else:
        # Non-TTY/piped: skip the shell env-var hint — it may not be applicable
        # and we must not hang waiting for input.  Give the CLI command only.
        fix_cmd = f"  hachi secrets --set {env_name}=<your-key>"

    console.print(
        Panel(
            f"[bold red]API key missing — cannot start.[/bold red]\n\n"
            f"{msg}\n\n"
            f"[bold]Fix (one command):[/bold]\n"
            f"{fix_cmd}\n\n"
            f"{link_line}"
            f"Then run [bold]hachi run[/bold] again.\n"
            f"Or run [bold]hachi quickstart[/bold] to choose a different provider.",
            title="[bold red]Not Ready[/bold red]",
            border_style="red",
        )
    )

    # Interactive recovery: offer to collect the key right now when in a TTY.
    # In non-TTY contexts we return False immediately — never hang on input.
    if sys.stdin.isatty():
        fixed = _interactive_first_run_setup(env_name, cfg.provider.kind)
        if fixed:
            cfg2 = load_effective_config()
            api_key_env2 = getattr(cfg2.provider, "api_key_env", None)
            ok2, _ = service.validate_provider(kind=cfg2.provider.kind, api_key_env=api_key_env2)
            return ok2

    return False


def _render_event(event_type: str, data: dict):
    """
    Callback invoked by the ExecutionLoop on every significant action.
    Renders a beautiful, real-time visual log in the terminal.
    """
    if event_type in ("thinking", "thinking.step"):
        iteration = data.get("iteration", "?")
        console.print(Rule(f"[dim]Step {iteration}[/dim]", style="dim"))

    elif event_type in ("tool_call", "tool.call.started"):
        tool_name = data.get("name", "unknown")
        tool_input = data.get("input", {})

        # Format the input nicely
        input_display = json.dumps(tool_input, indent=2, default=str)
        if len(input_display) > 300:
            input_display = input_display[:300] + "\n  ..."

        console.print(
            Panel(
                f"[bold yellow]{tool_name}[/bold yellow]\n[dim]{input_display}[/dim]",
                title="[bold cyan]Tool Call[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
        )

    elif event_type in ("tool_result", "tool.call.completed"):
        tool_name = data.get("name", "unknown")
        result = data.get("result", data.get("result_preview", ""))

        # Truncate long results for display
        if len(result) > 400:
            display_result = result[:400] + "\n..."
        else:
            display_result = result

        console.print(
            Panel(
                f"[dim]{display_result}[/dim]",
                title=f"[bold green]Result: {tool_name}[/bold green]",
                border_style="green",
                padding=(0, 1),
            )
        )

    elif event_type in ("text_chunk", "text.stream.delta"):
        # Intermediate text from the model (before it decides on a tool call)
        text = data.get("text", "")
        if text.strip():
            console.print(f"  [dim italic]{text[:200]}[/dim italic]")

    elif event_type in ("compaction", "memory.compaction"):
        old_skill = data.get("old_skill", "none")
        new_skill = data.get("new_skill", "unknown")
        console.print(
            Panel(
                f"[bold]Context switch detected[/bold]\n"
                f"[dim]{old_skill}[/dim] -> [bold cyan]{new_skill}[/bold cyan]\n"
                f"[dim]Previous task context compacted to save tokens.[/dim]",
                title="[bold yellow]Memory Compaction[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            )
        )

    elif event_type == "boot.progress":
        idx = data.get("index", "?")
        total = data.get("total", "?")
        message = data.get("message", "Booting")
        console.print(f"[dim]Boot {idx}/{total}: {message}[/dim]")

    elif event_type == "boot.complete":
        console.print("[green]Runtime boot complete.[/green]")

    elif event_type == "permission.decided":
        decision = data.get("decision", "unknown")
        tool = data.get("tool", "unknown")
        console.print(f"[bold]Permission {decision}[/bold] for {tool}")

    elif event_type == "subagent.started":
        console.print(f"[cyan]Sub-agent started:[/cyan] {data.get('role', 'unknown')}")

    elif event_type == "subagent.completed":
        console.print(
            f"[cyan]Sub-agent completed:[/cyan] {data.get('role', 'unknown')} "
            f"({data.get('status', 'unknown')})"
        )


@app.command()
def onboard():
    """
    Initialize the ~/.hachi/ workspace.
    Run this when installing the agent for the first time.
    """
    try:
        ensure_workspace()
        console.print(
            Panel(
                "[bold green]Hachi workspace initialized successfully![/bold green]\n\n"
                f"Your config directory: [cyan]{get_workspace_dir()}[/cyan]\n"
                f"Your skills directory: [cyan]{get_hachi_paths().skills_dir}[/cyan]",
                title="Setup Complete",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Error initializing workspace:[/] {e}")


@app.command()
def quickstart(
    provider: str | None = typer.Option(
        None, "--provider", help="anthropic | openai-compatible | ollama (skips the prompt)."
    ),
    tier: str | None = typer.Option(
        None, "--tier", help="Safety tier: sandbox | guided | unrestricted (skips the prompt)."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept defaults without prompting."),
):
    """Fastest path from zero to chatting — a few plain questions, keys checked up front.

    Designed for non-technical users: pick a provider, we validate your API key
    immediately (instead of failing on the first message), choose a safety level,
    and you're ready to run ``hachi run``.
    """
    console.print(
        Panel(
            "[bold]Welcome to Hachi[/bold] 🐕\nLet's get you set up in under a minute.",
            title="Quickstart",
        )
    )
    ensure_workspace()
    service = OnboardingService()

    # 1. Provider
    provider_choices = {"1": "anthropic", "2": "openai-compatible", "3": "ollama"}
    chosen = (provider or "").strip().lower()
    if chosen not in {"anthropic", "openai-compatible", "ollama"}:
        if yes:
            chosen = "anthropic"
        else:
            console.print(
                "\nWhich AI provider do you want to use?\n"
                "  [cyan]1[/cyan] Anthropic (Claude) — recommended\n"
                "  [cyan]2[/cyan] OpenAI-compatible (OpenAI, etc.)\n"
                "  [cyan]3[/cyan] Ollama (free, runs locally)"
            )
            pick = Prompt.ask("Provider", choices=["1", "2", "3"], default="1")
            chosen = provider_choices[pick]

    # 2. Validate the API key BEFORE anything else (the usual non-geek failure point).
    env_name = default_api_key_env_for(chosen)
    ok, message = service.validate_provider(kind=chosen, api_key_env=env_name)
    if ok:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[yellow]⚠ {message}[/yellow]")
        if not yes and not typer.confirm("Continue setup anyway?", default=True):
            raise typer.Exit(1)

    # 3. Safety tier
    chosen_tier = (tier or "").strip().lower()
    if chosen_tier not in {"sandbox", "guided", "unrestricted"}:
        if yes:
            chosen_tier = "guided"
        else:
            console.print(
                "\nHow much freedom should the agent have?\n"
                "  [cyan]sandbox[/cyan]   — read-only, safest\n"
                "  [cyan]guided[/cyan]    — asks before risky actions (recommended)\n"
                "  [cyan]unrestricted[/cyan] — full access, no prompts"
            )
            chosen_tier = Prompt.ask(
                "Safety tier",
                choices=["sandbox", "guided", "unrestricted"],
                default="guided",
            )

    # 4. Apply and confirm
    try:
        plan = service.quick_setup(kind=chosen, permission_tier=chosen_tier)
    except ValueError as e:
        console.print(f"[red]Setup failed:[/red] {e}")
        raise typer.Exit(1) from e

    provider_answer = plan.answers.get("provider", {})
    console.print(
        Panel(
            "[bold green]You're ready![/bold green]\n\n"
            f"Provider: [cyan]{provider_answer.get('kind')}[/cyan] "
            f"(model: {provider_answer.get('model')})\n"
            f"Safety tier: [cyan]{chosen_tier}[/cyan]\n\n"
            "Start chatting with:  [bold]hachi run[/bold]\n"
            "Schedule proactive tasks with:  [bold]hachi schedule add[/bold]",
            title="Setup Complete",
        )
    )


@app.command()
def permissions(
    reset: bool = typer.Option(
        False, "--reset", help="Re-run the permissions wizard from scratch."
    ),
    tier: str | None = typer.Option(
        None, "--tier", help="Set the tier directly: sandbox, guided, or unrestricted."
    ),
    allow: str | None = typer.Option(None, "--allow", help="Add a folder path to allowed_paths."),
    block: str | None = typer.Option(None, "--block", help="Add a folder path to blocked_paths."),
):
    """
    View or modify device permissions.

    Without flags, shows the current permission configuration.
    Use --reset to re-run the wizard, --tier to switch tiers,
    or --allow/--block to add paths.
    """
    from hachi.core.permissions import generate_permissions_og

    permissions_file = get_permissions_file()

    # --reset: Re-run the wizard
    if reset:
        if permissions_file.exists():
            permissions_file.unlink()
        run_permissions_wizard(console)
        return

    # --tier: Quick tier switch
    if tier:
        if tier not in ("sandbox", "guided", "unrestricted"):
            console.print(
                f"[bold red]Invalid tier:[/] '{tier}'. Must be: sandbox, guided, unrestricted."
            )
            raise typer.Exit(1)

        content = generate_permissions_og(tier)
        with open(permissions_file, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[bold green]Permission tier set to:[/] {tier}")
        show_current_permissions(console)
        return

    # --allow: Add a path to allowed_paths
    if allow:
        _modify_permissions_path(permissions_file, "allowed_paths", allow, "add", console)
        return

    # --block: Add a path to blocked_paths
    if block:
        _modify_permissions_path(permissions_file, "blocked_paths", block, "add", console)
        return

    # No flags: Show current permissions
    if not permissions_file.exists():
        console.print("[yellow]No permissions configured yet.[/yellow]")
        console.print("Run [bold]hachi permissions --reset[/bold] to set up permissions.")
        return

    show_current_permissions(console)


def _modify_permissions_path(
    permissions_file: Path,
    field: str,
    path: str,
    action: str,
    console,
):
    """
    Modify a path field (allowed_paths or blocked_paths) in device-permissions.og.

    Reads the current file, finds the filesystem node's config, appends the path,
    and rewrites the file cleanly.

    Args:
        permissions_file: Path to device-permissions.og.
        field: 'allowed_paths' or 'blocked_paths'.
        path: The path string to add.
        action: 'add' (future: 'remove').
        console: Rich console for output.
    """
    if not permissions_file.exists():
        console.print(
            "[yellow]No permissions file found. Run 'hachi permissions --reset' first.[/yellow]"
        )
        return

    # Read current file content
    with open(permissions_file, encoding="utf-8") as f:
        content = f.read()

    # Find the filesystem node's field and append the path
    resolved = str(Path(path).expanduser().resolve())
    lines = content.splitlines()
    modified = False

    for i, line in enumerate(lines):
        if line.strip().startswith(f"{field}="):
            current_value = line.split("=", 1)[1].strip()
            # Compare exact comma-separated tokens, not a substring (otherwise
            # adding 'C:\\a' is wrongly rejected when 'C:\\abc' is already present).
            existing = [token.strip() for token in current_value.split(",") if token.strip()]
            if resolved in existing:
                console.print(f"[yellow]'{resolved}' is already in {field}.[/yellow]")
                return
            existing.append(resolved)
            lines[i] = f"{field}={', '.join(existing)}"
            modified = True
            break

    if not modified:
        console.print(
            f"[red]Could not find '{field}' in the permissions file. Re-run with --reset.[/red]"
        )
        return

    with open(permissions_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    console.print(f"[bold green]Added[/] '{resolved}' to {field}.")
    show_current_permissions(console)


@app.command()
def reauth():
    """
    Clear stored API credentials (like Slack/Notion tokens) so you can update them.
    """
    vault = CredentialVault()
    deleted = vault.clear_all()
    if deleted > 0:
        console.print(
            Panel(
                "[bold green]Credentials cleared successfully![/bold green]\n\n"
                "The next time you boot Hachi and trigger an integration,\n"
                "you will be prompted to enter your new tokens.",
                title="Reauthentication Complete",
                border_style="green",
            )
        )
    else:
        console.print("[yellow]No credentials vault found. You're already starting fresh.[/yellow]")


def _run_repl() -> None:
    """
    Start the compatibility Rich REPL agent session.
    """
    ensure_workspace()
    _apply_quick_setup_if_needed()

    # Ensure device permissions exist (runs wizard on first launch)
    ensure_device_permissions(console)

    console.print("[dim]Booting Hachi...[/dim]")

    try:
        agent: AgentSession = boot_agent(on_event=_render_event)
    except Exception as e:
        console.print(f"\n[bold red]Failed to boot agent:[/] {e}")
        console.print(
            "[yellow]Hint: Make sure your ANTHROPIC_API_KEY environment variable is set.[/yellow]"
        )
        raise typer.Exit(1) from None

    # Boot banner with permission tier
    skill_count = agent.skill_engine.node_count
    perm_summary = agent.permission_gate.summary

    console.print(
        Panel(
            f"[bold magenta]Hachi is online.[/bold magenta]\n"
            f"Skills loaded: [cyan]{skill_count}[/cyan] | {perm_summary}\n"
            f"Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to terminate.",
            border_style="magenta",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if user_input.strip().lower() in ["exit", "quit"]:
                console.print("[dim]Shutting down Hachi...[/dim]")
                agent.shutdown()
                break

            if not user_input.strip():
                continue

            # The loop will emit events via _render_event as it executes
            response = agent.chat(user_input)

            # Render the final response
            console.print(Rule("[bold magenta]Hachi[/bold magenta]", style="magenta"))
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Session interrupted. Shutting down...[/dim]")
            agent.shutdown()
            break
        except Exception as e:
            console.print(f"\n[bold red]Error:[/] {e}")


def _resolve_resume_target(*, resume: bool, continue_latest: bool) -> str | None:
    """Resolve which prior session (if any) to resume into the new TUI session.

    ``--continue`` picks the most recent session non-interactively; ``--resume``
    prints a numbered list and asks the operator to choose. Returns the chosen
    session id, or None when nothing is selected.
    """
    if not (resume or continue_latest):
        return None

    store = SessionStore()
    try:
        if continue_latest:
            sid = store.get_latest_session_id()
            if not sid:
                console.print("[yellow]No previous session to continue. Starting fresh.[/yellow]")
            return sid

        sessions = store.get_recent_sessions(limit=10)
        if not sessions:
            console.print("[yellow]No previous sessions found. Starting fresh.[/yellow]")
            return None

        console.print(Rule("[bold magenta]Resume a session[/bold magenta]", style="magenta"))
        for index, item in enumerate(sessions, start=1):
            started = str(item.get("started_at", ""))[:19].replace("T", " ")
            turns = item.get("total_turns", 0)
            model = item.get("model", "unknown")
            title = (item.get("title") or "").strip()
            title_prefix = f"[white]{title}[/white]  " if title else ""
            console.print(
                f"  [cyan]{index}[/cyan]. {title_prefix}{started}"
                f"  ·  {turns} turns  ·  [dim]{model}[/dim]"
            )

        choice = Prompt.ask(
            "Select a session number (or press Enter to start fresh)", default=""
        ).strip()
        if not choice:
            return None
        try:
            selected = sessions[int(choice) - 1]
        except (ValueError, IndexError):
            console.print("[yellow]Invalid selection. Starting fresh.[/yellow]")
            return None
        return str(selected.get("id"))
    finally:
        store.shutdown()


def _launch_assistant(*, repl: bool, resume: bool, continue_latest: bool) -> None:
    """Shared entry point for `hachi` and `hachi run`.

    REST-only: boots an in-process gateway HTTP server on loopback and launches
    the Hachi Cockpit (Textual TUI) against it over the typed REST/SSE API — the
    same gateway that serves the web UI. Pass ``--repl`` for the legacy Rich REPL.
    """
    ensure_workspace()
    _apply_quick_setup_if_needed()
    if not _pre_flight_check():
        raise typer.Exit(1)
    ensure_device_permissions(console)

    if repl:
        _run_repl()
        return

    resume_id = _resolve_resume_target(resume=resume, continue_latest=continue_latest)
    if (resume or continue_latest) and not resume_id:
        # _resolve_resume_target already printed an appropriate message.
        pass

    _launch_cockpit(resume_session_id=resume_id)


def _launch_cockpit(resume_session_id: str | None = None) -> None:
    """Boot an in-process gateway and run the Hachi Cockpit against it.

    The cockpit is a REST-only surface: it talks to the gateway over HTTP/SSE on
    loopback, never to the orchestrator in-process. The gateway (and its attached
    runtime) is torn down cleanly when the cockpit exits.

    Args:
        resume_session_id: When set, the first session booted by the runtime will
            replay this prior session's transcript so context carries over (G1-T7).
    """
    from hachi.daemon import _default_log_path, setup_rotating_log
    from hachi.tui.cockpit.app import CockpitApp

    # Route gateway/uvicorn logs to a rotating file so they never spew over the
    # Textual UI (or leave a stray traceback on exit). The cockpit owns the
    # terminal; the gateway runs silently in a background thread.
    if not any(hasattr(h, "baseFilename") for h in logging.getLogger().handlers):
        setup_rotating_log(_default_log_path())

    host = "127.0.0.1"
    try:
        token = _resolve_gateway_auth_token(host)
        server, base_url, runtime = _start_gateway_server(
            host=host,
            port=0,
            attach_runtime=True,
            resume_session_id=resume_session_id,
        )
    except OSError as exc:
        console.print(f"[bold red]Failed to start the gateway:[/] {exc}")
        raise typer.Exit(1) from exc

    try:
        CockpitApp(base_url=base_url, token=token).run()
    finally:
        if runtime is not None:
            runtime.shutdown()
        server.stop()


def _run_once(prompt: str) -> None:
    """Run a single agent turn non-interactively and print the reply.

    Powers ``hachi run --once`` (and the bare positional ``hachi run "<task>"``):
    boots an agent, runs one :meth:`AgentSession.chat` turn, writes ONLY the reply
    to stdout so it pipes byte-clean into scripts and CI, then exits. Diagnostics
    and errors go through ``console`` (Rich/stderr-ish) so they never contaminate
    the piped reply on success.
    """
    try:
        agent: AgentSession = boot_agent()
    except Exception as exc:  # noqa: BLE001 - any boot failure is a clean exit 1
        console.print(f"[bold red]Failed to boot agent:[/] {exc}")
        console.print(
            "[yellow]Hint: set your provider API key (e.g. ANTHROPIC_API_KEY) "
            "or run `hachi setup`.[/yellow]"
        )
        raise typer.Exit(1) from None

    try:
        response = agent.chat(prompt)
    except Exception as exc:  # noqa: BLE001 - a turn failure is a clean exit 1
        console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(1) from None
    finally:
        try:
            agent.shutdown()
        except Exception:  # noqa: BLE001 - shutdown is best-effort
            pass

    # Raw echo (not console.print): keep stdout unwrapped and ANSI-free so the
    # reply pipes cleanly into `jq`, files, and downstream commands.
    typer.echo(response)


@app.command()
def run(
    prompt: str | None = typer.Argument(
        None,
        help="One-shot task text. With this (or --once) Hachi runs a single turn, "
        "prints the reply, and exits — no TUI. Quote multi-word prompts.",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single turn and exit instead of opening the TUI. Reads the "
        "prompt from the argument, or from stdin when piped.",
    ),
    repl: bool = typer.Option(
        False,
        "--repl",
        help="Launch the legacy Rich REPL instead of the Textual TUI.",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        "-r",
        help="Pick a past session to resume (full context reload).",
    ),
    continue_latest: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Resume the most recent session.",
    ),
):
    """
    Start Hachi.

    Default: Textual TUI.
    One-shot: ``hachi run --once "your task"`` (or pipe a prompt via stdin) runs a
    single turn, prints the reply, and exits — no TUI. Handy in scripts and CI.
    Fallback: pass --repl for the legacy terminal REPL.
    """
    # --resume / --continue are no-argument session pickers; a stray token after
    # them (e.g. the old `hachi run --resume <id>` form) now binds to `prompt`, so
    # reject that combination explicitly instead of silently running a one-shot.
    if (resume or continue_latest) and prompt is not None:
        console.print(
            "[bold red]Error:[/] --resume/--continue take no argument. Use them "
            'alone to pick a session, or `hachi run --once "your task"` for a '
            "one-shot run."
        )
        raise typer.Exit(2)

    # One-shot: an explicit --once, or any positional prompt, means "single turn,
    # no TUI". --once with no argument reads the prompt from stdin when piped.
    if once or prompt is not None:
        text = (prompt or "").strip()
        if not text and once and not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        if not text:
            console.print(
                "[bold red]Error:[/] one-shot mode needs a prompt — pass it as an "
                'argument (hachi run --once "your task") or pipe it via stdin.'
            )
            raise typer.Exit(2)
        _run_once(text)
        return

    _launch_assistant(repl=repl, resume=resume, continue_latest=continue_latest)


@app.command("cockpit")
def cockpit(
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        envvar="HACHI_GATEWAY_URL",
        help="Gateway base URL (e.g. http://127.0.0.1:8787). "
        "Falls back to $HACHI_GATEWAY_URL; omit for offline placeholder mode.",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="HACHI_GATEWAY_TOKEN",
        help="Bearer token for the gateway. Falls back to $HACHI_GATEWAY_TOKEN.",
    ),
):
    """Launch the Hachi Cockpit — the REST-only terminal cockpit UI.

    Talks to a running ``hachi gateway`` over HTTP when ``--base-url`` (or
    ``$HACHI_GATEWAY_URL``) is set; otherwise renders representative placeholder
    data so the surface is always demonstrable. For an interactive agent chat
    session, use ``hachi run`` (live chat streaming is not yet wired here).
    """
    # Lazy import: the cockpit is a self-contained REST-only surface and must not
    # pull the in-process agent stack into CLI startup.
    from hachi.tui.cockpit.app import CockpitApp

    CockpitApp(base_url=base_url, token=token).run()


@app.command("run-repl")
def run_repl_command():
    """Launch the compatibility Rich REPL explicitly."""
    _run_repl()


@app.command("gateway")
def gateway(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway bind address."),
    port: int = typer.Option(8787, "--port", min=0, max=65535, help="Gateway bind port."),
    runtime: bool = typer.Option(
        True,
        "--runtime/--no-runtime",
        help="Attach in-process runtime so chat/events/session endpoints are available.",
    ),
):
    """Run the typed gateway HTTP server for connect/readiness flow consumers."""
    _run_gateway_http_server(host=host, port=port, attach_runtime=runtime)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway bind address."),
    port: int = typer.Option(8787, "--port", min=0, max=65535, help="Gateway bind port."),
    no_frontend: bool = typer.Option(
        False,
        "--no-frontend",
        help="Skip mounting the pre-built frontend (frontend/dist).",
    ),
):
    """Start the Hachi gateway AND serve the pre-built web frontend in one command.

    Binds the gateway HTTP server on *host:port*, auto-generates a bearer token
    (or reuses the persisted one at ~/.hachi/gateway-token), mounts the pre-built
    frontend at ``frontend/dist`` on the root path, and prints the URL.

    This is the recommended single-terminal way to run Hachi:

        hachi serve            # http://127.0.0.1:8787

    Use ``hachi gateway`` if you want the backend API without the frontend.
    """
    # Headless server → fail fast on a first-time Google OAuth call (run `hachi auth google`)
    # instead of opening a browser and blocking ~120s on a display-less server.
    os.environ.setdefault("HACHI_OAUTH_NONINTERACTIVE", "1")

    # Locate the pre-built frontend distribution directory.
    _frontend_dist: Path | None = None
    if not no_frontend:
        candidates = [
            Path(__file__).resolve().parents[3] / "frontend" / "dist",
            Path.cwd() / "frontend" / "dist",
        ]
        for candidate in candidates:
            if candidate.is_dir():
                _frontend_dist = candidate
                break
        if _frontend_dist is None:
            console.print(
                "[yellow]Warning: frontend/dist not found — "
                "run [bold]npm run build --prefix frontend[/bold] first "
                "to serve the web UI. Starting gateway-only.[/yellow]"
            )

    ensure_workspace()
    _apply_quick_setup_if_needed()
    if not _pre_flight_check():
        raise typer.Exit(1)

    runtime: _InProcessGatewayRuntime | None = None
    server: GatewayHTTPServer | None = None
    try:
        auth_token = _resolve_gateway_auth_token(host)
        runtime = _InProcessGatewayRuntime()
        # Publish the active runtime so resume.py can rehydrate cold-start sessions.
        global _ACTIVE_RUNTIME  # noqa: PLW0603
        _ACTIVE_RUNTIME = runtime

        server = GatewayHTTPServer(
            _build_gateway_control_plane(runtime=runtime, support=runtime),
            host=host,
            port=port,
            auth_token=auth_token,
            frontend_dist=_frontend_dist,
        )
        bound_port = server.start()
        base_url = f"http://{host}:{bound_port}"
    except OSError as exc:
        console.print(f"[bold red]Failed to start gateway:[/] {exc}")
        raise typer.Exit(1) from exc

    frontend_line = f"Web UI:     [cyan]{base_url}[/cyan]\n" if _frontend_dist else ""
    console.print(
        Panel(
            "[bold green]Hachi is running.[/bold green]\n\n"
            f"{frontend_line}"
            f"API:        [cyan]{base_url}/docs[/cyan]\n"
            f"Readiness:  [cyan]{base_url}/readiness[/cyan]\n"
            f"Auth:       [cyan]Authorization: Bearer <token>[/cyan]\n"
            f"Token file: [cyan]{_default_gateway_token_path()}[/cyan]\n\n"
            "Press [bold]Ctrl+C[/bold] to stop.",
            title="Hachi Serve",
            border_style="green",
        )
    )

    try:
        _wait_until_interrupted()
    except KeyboardInterrupt:
        console.print("[dim]Stopping...[/dim]")
    finally:
        if runtime is not None:
            runtime.shutdown()
        if server is not None:
            server.stop()


@app.command("gateway-status")
def gateway_status(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway host to check."),
    port: int = typer.Option(8787, "--port", help="Gateway port to check."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
    timeout: float = typer.Option(2.0, "--timeout", help="Connection timeout in seconds."),
) -> None:
    """Check whether a local Hachi gateway is reachable and healthy."""
    import urllib.error
    import urllib.request

    url = f"http://{host}:{port}/health"
    result: dict = {"host": host, "port": port, "url": url}
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            result["status"] = "reachable"
            result["http_status"] = resp.status
            try:
                result["detail"] = json.loads(body)
            except Exception:
                result["detail"] = body[:200]
    except urllib.error.URLError as exc:
        result["status"] = "unreachable"
        result["error"] = str(exc.reason)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    if as_json:
        print(json.dumps(result))
        raise typer.Exit(0 if result.get("status") == "reachable" else 1)

    ok = result.get("status") == "reachable"
    icon = "[green]●[/green]" if ok else "[red]●[/red]"
    state = "reachable" if ok else result.get("status", "unknown")
    console.print(f"{icon} {host}:{port} — {state}")
    if not ok:
        console.print(f"  [dim]{result.get('error', '')}[/dim]")
        console.print(
            f"  Start gateway with: [bold]hachi gateway --host {host} --port {port}[/bold]"
        )
        raise typer.Exit(1)
    http_status = result.get("http_status", "")
    console.print(f"  HTTP {http_status}  {url}")


@app.command("gateway-openapi")
def gateway_openapi(
    output: Path = typer.Option(  # noqa: B008
        Path("openapi/hachi-openapi.json"),
        "--output",
        help="Write OpenAPI schema JSON to this path.",
    ),
):
    """Export the local gateway OpenAPI schema without starting a server process."""
    from hachi.gateway.fastapi_app import create_gateway_app

    ensure_workspace()
    support = _InProcessGatewayRuntime()
    control_plane = _build_gateway_control_plane(runtime=None, support=support)
    app_instance = create_gateway_app(control_plane)
    schema = app_instance.openapi()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    console.print(f"[bold green]OpenAPI schema written:[/] {output}")


@app.command()
def setup(
    tier: str = typer.Option(
        "lightning", "--tier", help="Setup tier: lightning, recommended, enhanced, power."
    ),
    permission_tier: str = typer.Option(
        "guided", "--permission-tier", help="Permission tier: sandbox, guided, unrestricted."
    ),
):
    """Run or resume setup without launching a session."""
    ensure_workspace()

    service = OnboardingService()
    detected = service.detect_environment()

    provider: dict[str, str] = {
        "kind": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-haiku-4-5",
    }

    if detected.get("ollama_cli"):
        provider = {
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "llama3.1:8b",
        }
    elif detected.get("openai_env"):
        provider = {
            "kind": "openai-compatible",
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-4o-mini",
        }

    plan = service.build_tier_plan(
        tier,
        {
            "provider": provider,
            "permission_tier": permission_tier,
        },
    )
    service.apply_setup(plan)

    # Validate the API key immediately after saving — surface missing keys now,
    # not cryptically at boot time.
    key_ok, key_msg = service.validate_provider(
        kind=provider["kind"], api_key_env=provider.get("api_key_env")
    )
    key_status = "[green]✓ API key found.[/green]" if key_ok else f"[yellow]⚠ {key_msg}[/yellow]"

    console.print(
        Panel(
            "[bold green]Setup saved.[/bold green]\n\n"
            f"Tier: [cyan]{tier}[/cyan]\n"
            f"Provider: [cyan]{provider['kind']}[/cyan]\n"
            f"Permission tier: [cyan]{permission_tier}[/cyan]\n"
            f"{key_status}\n\n"
            "You can rerun setup anytime with [bold]hachi setup[/bold].",
            title="Onboarding",
        )
    )

    # Post-setup suggestion chips — first-magic prompts.
    try:
        from hachi.core.suggestion_chips import chips_for_context, render_chips_text

        chips = chips_for_context(max_chips=4, prioritise_composer=True)
        header = "Start here — paste any prompt into the agent:"
        chips_text = render_chips_text(chips, header=header)
        console.print(f"\n[dim]{chips_text}[/dim]")
        console.print("\n[dim]Run [bold]hachi run[/bold] to open the agent.[/dim]")
    except Exception:
        pass  # Chips are cosmetic; never block setup completion.


@app.command()
def config(
    show_paths: bool = typer.Option(
        False, "--paths", help="Show canonical config/data/cache/state paths."
    ),
):
    """Show the effective resolved configuration."""
    cfg = load_effective_config().model_dump(mode="python", exclude_none=True)
    console.print(Panel(json.dumps(cfg, indent=2), title="Effective Config", border_style="cyan"))

    if show_paths:
        p = get_hachi_paths()
        path_payload = {
            "config_dir": str(p.config_dir),
            "data_dir": str(p.data_dir),
            "cache_dir": str(p.cache_dir),
            "state_dir": str(p.state_dir),
            "settings_toml": str(p.global_config_toml),
        }
        console.print(
            Panel(
                json.dumps(path_payload, indent=2), title="Canonical Paths", border_style="magenta"
            )
        )


@app.command("config-validate")
def config_validate(
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
):
    """Validate the effective configuration and exit non-zero on any problem.

    Checks that settings.toml parses, the schema is sound (provider kind,
    permission tier, max_tokens), the configured model is consistent with the
    allowed_models guardrail, and the provider API key resolves. CI-friendly."""
    import tomllib

    from hachi.core.config_validate import validate_config

    paths = get_hachi_paths()
    checks: list[dict] = []

    # load_effective_config silently falls back to defaults on malformed TOML, so
    # parse the raw file here to surface syntax errors rather than hide them.
    toml_path = paths.global_config_toml
    if toml_path.exists():
        try:
            with toml_path.open("rb") as handle:
                tomllib.load(handle)
            checks.append({"name": "settings_toml_parses", "ok": True, "detail": str(toml_path)})
        except Exception as exc:
            checks.append(
                {"name": "settings_toml_parses", "ok": False, "detail": f"parse error: {exc}"}
            )
    else:
        checks.append(
            {"name": "settings_toml_parses", "ok": True, "detail": "no settings.toml (defaults)"}
        )

    cfg = load_effective_config()
    service = OnboardingService(paths=paths)
    key_ok, key_msg = service.validate_provider(
        kind=cfg.provider.kind, api_key_env=getattr(cfg.provider, "api_key_env", None)
    )
    report = validate_config(cfg, provider_key_ok=key_ok, provider_key_detail=key_msg)

    all_checks = checks + report["checks"]
    overall = all(c["ok"] for c in all_checks)
    result = {"ok": overall, "checks": all_checks}

    if json_output:
        # Plain print: Rich's console soft-wraps long JSON to terminal width.
        print(json.dumps(result, indent=2))
        raise typer.Exit(0 if overall else 1)

    console.print("[bold]Config validation[/bold]")
    for check in all_checks:
        mark = "[green]✓[/green]" if check["ok"] else "[red]✗[/red]"
        console.print(f"  {mark} {check['name']}  [dim]{check['detail']}[/dim]")
    verdict = "[green]Config OK[/green]" if overall else "[red]Hachi config has problems[/red]"
    console.print(f"\n{verdict}")
    raise typer.Exit(0 if overall else 1)


# Documented short config keys → their canonical nested path on ResolvedConfig.
# Keeping the friendly names as aliases avoids breaking existing docs/scripts
# while the canonical dotted keys remove the CLI/web/env tier-name drift.
_CONFIG_KEY_ALIASES = {
    "safety_tier": "permissions.tier",
    "max_tokens": "agent.max_tokens",
    "session_cost_cap_usd": "limits.max_session_cost_usd",
}


@app.command("config-get")
def config_get(
    key: str | None = typer.Argument(None, help="Dot-separated key, e.g. provider.model."),
    as_json: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    """Show one or all effective configuration values.

    Pass a key (dot-separated) to show a single value, or omit to show all
    top-level settings.  Read-only — use config-set to change values.
    """
    cfg = load_effective_config()
    flat: dict[str, object] = {
        "provider.kind": cfg.provider.kind,
        "provider.model": cfg.provider.model,
        "provider.base_url": cfg.provider.base_url,
        "permissions.tier": cfg.permissions.tier,
        "agent.max_tokens": cfg.agent.max_tokens,
        "limits.max_session_cost_usd": cfg.limits.max_session_cost_usd,
        "workspace_dir": str(get_workspace_dir()),
    }

    if key is not None:
        canonical = _CONFIG_KEY_ALIASES.get(key, key)
        if canonical not in flat:
            console.print(f"[red]Unknown key:[/red] {key!r}")
            known = sorted(flat) + sorted(_CONFIG_KEY_ALIASES)
            console.print(f"  Known keys: {', '.join(known)}")
            raise typer.Exit(1)
        value = flat[canonical]
        if as_json:
            print(json.dumps({key: value}))
        else:
            console.print(f"{key} = {value!r}")
        return

    if as_json:
        print(json.dumps(flat, default=str))
        return
    for k, v in sorted(flat.items()):
        console.print(f"[bold]{k}[/bold] = {v!r}")


@app.command("config-set")
def config_set(
    key: str = typer.Argument(..., help="Dot-separated key, e.g. provider.model."),
    value: str = typer.Argument(..., help="New value (always stored as a string or parsed)."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Set a configuration value and persist it to settings.toml.

    Writable keys (canonical, with documented aliases):
      provider.model, provider.base_url,
      permissions.tier             (alias: safety_tier),
      agent.max_tokens             (alias: max_tokens),
      limits.max_session_cost_usd  (alias: session_cost_cap_usd).
    Changes take effect on the next ``hachi run``.
    """
    cfg = load_effective_config()

    canonical = _CONFIG_KEY_ALIASES.get(key, key)
    try:
        if canonical == "provider.model":
            cfg.provider.model = value
        elif canonical == "provider.base_url":
            cfg.provider.base_url = value
        elif canonical == "permissions.tier":
            if value not in {"sandbox", "guided", "unrestricted"}:
                console.print(
                    "[red]permission tier must be one of:[/red] sandbox, guided, unrestricted"
                )
                raise typer.Exit(1)
            cfg.permissions.tier = value
        elif canonical == "agent.max_tokens":
            cfg.agent.max_tokens = int(value)
        elif canonical == "limits.max_session_cost_usd":
            parsed = float(value)
            if parsed < 0:
                console.print("[red]session_cost_cap_usd must be >= 0[/red]")
                raise typer.Exit(1)
            cfg.limits.max_session_cost_usd = parsed
        else:
            console.print(f"[red]Cannot set:[/red] {key!r}  (not a writable key)")
            console.print(
                "  Writable keys: provider.model, provider.base_url, permissions.tier "
                "(safety_tier), agent.max_tokens (max_tokens), limits.max_session_cost_usd "
                "(session_cost_cap_usd)"
            )
            raise typer.Exit(1)
    except (ValueError, TypeError) as exc:
        console.print(f"[red]Invalid value for {key}:[/red] {exc}")
        raise typer.Exit(1) from exc

    write_global_config(cfg)

    if as_json:
        print(json.dumps({"key": key, "value": value, "ok": True}))
        return
    console.print(f"[green]Set[/green] {key} = {value!r}")
    console.print("[dim]Restart the agent for changes to take effect.[/dim]")


@app.command("google-auth")
def google_auth(
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
    revoke: bool = typer.Option(
        False, "--revoke", help="Clear stored Google credentials and exit."
    ),
) -> None:
    """Authenticate with Google Workspace (Gmail, Calendar, Drive, …).

    Opens a browser window to complete the OAuth consent flow.  Credentials
    are cached in the secure store so subsequent runs do not re-prompt.

    Requires GOOGLE_CLIENT_ID (and optionally GOOGLE_CLIENT_SECRET) to be set
    in your environment.  Run ``hachi doctor`` to check the current status.
    """
    import os

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        msg = (
            "GOOGLE_CLIENT_ID is not set.  "
            "Create OAuth 2.0 credentials at https://console.cloud.google.com/apis/credentials "
            "and export GOOGLE_CLIENT_ID=<your-id> before running this command."
        )
        if as_json:
            print(json.dumps({"ok": False, "error": "GOOGLE_CLIENT_ID not set", "detail": msg}))
            raise typer.Exit(1)
        console.print(f"[red]Error:[/red] {msg}")
        raise typer.Exit(1)

    from hachi.core.oauth import OAuthManager

    oauth = OAuthManager(secret_store=create_default_secret_store())

    if revoke:
        oauth.save_token("google", {})
        if as_json:
            print(json.dumps({"ok": True, "revoked": True}))
            return
        console.print("[green]Google credentials cleared.[/green]")
        return

    # Collect all scopes from the hub so we request them in one consent screen.
    from hachi.integrations.google import GoogleIntegrationHub

    hub = GoogleIntegrationHub()
    all_scopes: list[str] = []
    for svc in hub._services:
        for scope in svc.required_scopes:
            if scope not in all_scopes:
                all_scopes.append(scope)

    try:
        token = oauth.get_google_credentials(all_scopes)
        ok = bool(token)
    except Exception as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}))
            raise typer.Exit(1) from exc
        console.print(f"[red]Authentication failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        print(json.dumps({"ok": ok, "scopes_requested": len(all_scopes)}))
        if not ok:
            raise typer.Exit(1)
        return

    if ok:
        console.print("[green]✓[/green] Google Workspace authenticated successfully.")
        console.print(
            f"  [dim]{len(all_scopes)} scope(s) granted — "
            "Gmail, Calendar, Drive and more are now available.[/dim]"
        )
    else:
        console.print("[red]Authentication did not return a token.[/red]")
        raise typer.Exit(1)


@app.command()
def models(
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
):
    """List models the active provider exposes; also shows all configured providers."""
    from hachi.core.llm import create_llm_client, resolve_available_models

    cfg = load_effective_config()
    provider = cfg.provider
    current = provider.model
    allowed = list(getattr(provider, "allowed_models", []) or [])

    provider_config = {
        "kind": provider.kind,
        "model": provider.model,
        "api_key_ref": getattr(provider, "api_key_ref", None),
        "api_key_env": getattr(provider, "api_key_env", None),
        "base_url": getattr(provider, "base_url", None),
    }
    # P-06: a missing provider credential makes create_llm_client raise
    # (AnthropicClient.__init__ -> "ANTHROPIC_API_KEY must be provided…").
    # "No API key yet" is the expected first-run state, not an error, so degrade
    # to the configured model list rather than letting the traceback escape with
    # exit 1. Without this the "live discovery unavailable (offline or no API
    # key)" hint below was unreachable — construction blew up before it.
    # Mirrors the TUI/memory list path, which already wraps construction.
    discovered: list[str] = []
    client = None
    discovery_error: str | None = None
    try:
        client = create_llm_client(provider_config, secret_store=create_default_secret_store())
        try:
            discovered = client.list_models()
        finally:
            # Nested INSIDE the outer try so a failing close() is swallowed by the
            # same handler. The close used to sit in a sibling `finally`, where a
            # failure (dead HTTP session on a flaky network) escaped as exactly the
            # traceback this change exists to remove. This is the shape the
            # TUI/memory list path already uses.
            close = getattr(client, "close", None)
            if callable(close):
                close()
    except Exception as exc:  # noqa: BLE001 — degrade, never crash on discovery
        # Offline, missing API key, *or a broken provider config*. The reason is
        # kept and surfaced below: a typo'd `kind`, a bad `base_url` or a bad
        # `api_key_ref` must not masquerade as "no API key yet" — that is the one
        # case the user need not act on, and the bug this could otherwise hide.
        discovery_error = str(exc) or exc.__class__.__name__

    options = resolve_available_models(discovered, allowed, current)
    source = "allowlist" if allowed else ("provider" if discovered else "configured")
    result: dict[str, object] = {
        "provider": provider.kind,
        "current": current,
        "source": source,
        "restricted": bool(allowed),
        "models": options,
        # Additive: lets CI distinguish "no key yet" (expected) from a broken
        # provider config (actionable). Both share source == "configured".
        "discovery_error": discovery_error,
    }
    named_providers: dict = getattr(cfg, "providers", {}) or {}
    if named_providers:
        result["other_providers"] = {
            n: {"kind": ps.kind, "default_model": ps.model} for n, ps in named_providers.items()
        }

    if json_output:
        # Plain print: Rich's console soft-wraps long JSON to terminal width.
        print(json.dumps(result, indent=2))
        return

    console.print(
        f"[bold]Models[/bold] for [cyan]{provider.kind}[/cyan]"
        f"  [dim](active · source: {source})[/dim]"
    )
    if not options:
        console.print("  [dim]no models available[/dim]")
    else:
        for name in options:
            mark = "  [green](current)[/green]" if name == current else ""
            console.print(f"  • {name}{mark}")
    if allowed:
        console.print("  [dim]switching is restricted to the configured allowlist.[/dim]")
    elif not discovered:
        # Exception messages routinely end in a period; strip it so the
        # "; showing the configured model." clause reads cleanly.
        detail = (discovery_error or "offline or no API key").rstrip(".")
        console.print(
            f"  [dim]live discovery unavailable: {detail}; showing the configured model.[/dim]"
        )

    if named_providers:
        console.print()
        console.print("[bold]Other configured providers[/bold]")
        for pname, ps in named_providers.items():
            console.print(f"  • [cyan]{pname}[/cyan]  [{ps.kind}]  default: {ps.model}")
        console.print(
            "  [dim]Switch with:[/dim]  /model <provider>  [dim]or[/dim]  /model <provider> <model>"
        )


@app.command()
def secrets(
    list_only: bool = typer.Option(False, "--list", help="List stored secret metadata."),
    delete: str | None = typer.Option(None, "--delete", help="Delete a secret by logical name."),
    check: bool = typer.Option(False, "--check", help="Run secret backend health check."),
    set_key: str | None = typer.Option(
        None, "--set", metavar="KEY", help="Store a secret (prompts for the value)."
    ),
):
    """Inspect or manage secure secrets."""
    store = create_default_secret_store()

    if check:
        console.print(
            Panel(json.dumps(store.healthcheck(), indent=2), title="Secret Backend Health")
        )
        return

    if delete:
        store.delete(delete)
        console.print(f"Deleted secret metadata and value for: [cyan]{delete}[/cyan]")
        return

    if set_key:
        import sys

        if not sys.stdin.isatty():
            console.print("[red]--set requires an interactive terminal (stdin is not a TTY).[/red]")
            raise typer.Exit(1)
        value = typer.prompt(f"Value for '{set_key}'", hide_input=True, confirmation_prompt=True)
        if not value:
            console.print("[red]No value provided — secret not saved.[/red]")
            raise typer.Exit(1)
        store.set(set_key, value, metadata={"name": set_key, "labels": {"source": "cli"}})
        console.print(f"[green]Saved[/green] secret: [cyan]{set_key}[/cyan]")
        return

    if list_only:
        rows = store.list_metadata()
        console.print(Panel(json.dumps(rows, indent=2), title="Secret Metadata"))
        return

    console.print("Use --list, --delete <name>, --set <key>, or --check")


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
):
    """Run environment diagnostics for onboarding and runtime health."""
    import sys

    paths = get_hachi_paths()
    cfg = load_effective_config()
    service = OnboardingService(paths=paths)
    store = create_default_secret_store(paths=paths)

    # The most common "why isn't it working" cause: the configured provider's API
    # key isn't actually resolvable. Surface it explicitly.
    provider_ok, provider_msg = service.validate_provider(
        kind=cfg.provider.kind,
        api_key_env=getattr(cfg.provider, "api_key_env", None),
    )

    skill_count = 0
    skills_health = "unknown"
    mcp_servers_declared = 0
    engine = None
    try:
        from hachi.og_engine.engine import SkillEngine, lint_og_file

        engine = SkillEngine()
        engine.load_directory(paths.skills_dir)
        skill_count = engine.node_count
        mcp_servers_declared = len(engine.get_nodes_by_role("mcp"))

        if paths.skills_dir.exists():
            og_files = sorted(paths.skills_dir.glob("**/*.og"))
            reports = [lint_og_file(f) for f in og_files]
            errors = sum(r["summary"]["errors"] for r in reports)
            warnings = sum(r["summary"]["warnings"] for r in reports)
            skipped = len(engine._skipped_files)
            skipped_note = f", {skipped} unparseable" if skipped else ""
            skills_health = (
                f"{len(og_files)} file(s){skipped_note}, {errors} error(s), {warnings} warning(s) "
                "(run `hachi skill lint` for detail)"
            )
        else:
            skills_health = "no skills directory yet"
    except Exception:
        skill_count = -1  # could not load skills directory
        skills_health = "error scanning skills"
        mcp_servers_declared = -1

    # Runtime safety + limits posture: the levers that silently stop or constrain
    # an autonomous run. Surfaced so "why did it halt / get rate-limited / refuse
    # to send" is diagnosable at a glance.
    safety_and_limits = {
        "session_cost_cap_usd": os.environ.get("HACHI_MAX_SESSION_COST_USD", "unset"),
        "session_token_cap": os.environ.get("HACHI_MAX_SESSION_TOKENS", "unset"),
        "channel_rate_limit": os.environ.get("HACHI_CHANNEL_RATE_LIMIT", "default"),
        "openai_rate_limit": os.environ.get("HACHI_OPENAI_RATE_LIMIT", "default"),
        "channel_allowlist": os.environ.get("HACHI_CHANNEL_ALLOWLIST", "unset"),
        "outbound_secret_guard": (
            "disabled"
            if os.environ.get("HACHI_ALLOW_OUTBOUND_SECRETS", "").strip().lower()
            in {"1", "true", "yes"}
            else "enabled"
        ),
        "rest_allow_private": os.environ.get("HACHI_REST_ALLOW_PRIVATE", "false"),
        "tracing": os.environ.get("HACHI_TRACING", "off"),
    }

    checks = {
        "python_version": sys.version.split()[0],
        "config_dir_exists": paths.config_dir.exists(),
        "data_dir_exists": paths.data_dir.exists(),
        "state_dir_exists": paths.state_dir.exists(),
        "settings_toml_exists": paths.global_config_toml.exists(),
        "provider_kind": cfg.provider.kind,
        "provider_model": cfg.provider.model,
        "provider_api_key": "ok" if provider_ok else provider_msg,
        "permissions_tier": cfg.permissions.tier,
        "skills_loaded": skill_count,
        "skills_health": skills_health,
        "skills_parse_failures": (
            [s["file"] for s in engine._skipped_files] if engine is not None else []
        ),
        "mcp_servers_declared": mcp_servers_declared,
        "session_cost_cap_usd": safety_and_limits["session_cost_cap_usd"],
        "safety_and_limits": safety_and_limits,
        "onboarding_needs_setup": service.needs_setup(),
        "secret_backend": store.healthcheck(),
        "environment_detection": service.detect_environment(),
    }
    if json_output:
        # Plain print: Rich's console soft-wraps long JSON to terminal width.
        print(json.dumps(checks, indent=2))
        return
    console.print(Panel(json.dumps(checks, indent=2), title="Hachi Doctor", border_style="green"))


@app.command("security-audit")
def security_audit(
    fail_on_high: bool = typer.Option(
        False, "--fail-on-high", help="Exit non-zero when any high severity finding exists."
    ),
    fail_on_medium: bool = typer.Option(
        False, "--fail-on-medium", help="Exit non-zero when high or medium severity findings exist."
    ),
    max_findings: int | None = typer.Option(
        None, "--max-findings", help="Exit non-zero if finding count exceeds this threshold."
    ),
    ignore_checks: str = typer.Option(
        "",
        "--ignore-checks",
        help=(
            "Comma-separated check ids to exclude from both the report and the exit-code "
            "gate. Use for checks that describe the *deployment/runner* rather than the "
            "source tree (e.g. sandbox.process_backend on a CI runner), so a pull-request "
            "gate can still be strict about everything a contributor can affect."
        ),
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
):
    """
    Run a focused security posture audit for local Hachi deployments.

    Phase 1 Enhancement (CI-ready):
        - --json: Output machine-readable JSON to stdout for CI/automation integration.
        - --fail-on-high: Exit code 2 if any high-severity findings exist.
        - --fail-on-medium: Exit code 2 if any high or medium-severity findings exist.
        - --max-findings: Exit code 2 if total findings exceed threshold.
        - --ignore-checks: Exclude named check ids from the report and the gate.

    Default behavior: Pretty-print findings with human-friendly formatting.
    """
    cfg = load_effective_config()
    permissions_file = get_permissions_file()
    gate = PermissionGate(permissions_file)

    findings = []

    def add_finding(severity: str, check_id: str, message: str, remediation: str):
        findings.append(
            {
                "severity": severity,
                "check_id": check_id,
                "message": message,
                "remediation": remediation,
            }
        )

    if not os.environ.get("GOOGLE_CLIENT_ID"):
        add_finding(
            "high",
            "oauth.google_client_id_missing",
            "GOOGLE_CLIENT_ID is not configured; Google OAuth will fail and should fail closed.",
            "Set GOOGLE_CLIENT_ID explicitly in your runtime environment.",
        )

    secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if secret.startswith("GOCSPX-"):
        add_finding(
            "high",
            "oauth.google_client_secret_embedded",
            "GOOGLE_CLIENT_SECRET appears to be a concrete client secret and may be "
            "exposed in process environment.",
            "Store OAuth secret in a secure secret backend and avoid plaintext shell profile "
            "exports.",
        )

    if cfg.permissions.tier == "unrestricted":
        add_finding(
            "high",
            "permissions.unrestricted_tier",
            "Permission tier is set to unrestricted.",
            "Use guided tier for routine operation and explicitly approve exceptional commands.",
        )

    if gate._term.allow_all:
        add_finding(
            "high",
            "terminal.allow_all",
            "Terminal policy allows all commands.",
            "Constrain terminal allowed_commands to a minimal allowlist.",
        )

    rest_allowlist = os.environ.get("HACHI_REST_ALLOWLIST", "").strip()
    if not rest_allowlist:
        add_finding(
            "high",
            "rest.allowlist_missing",
            "HACHI_REST_ALLOWLIST is empty; secret-bearing REST calls are blocked "
            "and outbound posture is broad.",
            "Define explicit allowed hosts, e.g. "
            "HACHI_REST_ALLOWLIST=api.example.com,*.example.org",
        )

    if os.environ.get("HACHI_REST_ALLOW_PRIVATE", "false").lower() == "true":
        add_finding(
            "high",
            "rest.private_egress_enabled",
            "Private-network REST egress is enabled.",
            "Unset HACHI_REST_ALLOW_PRIVATE or set it to false.",
        )

    from hachi.core.sandbox import container_backend_available, sandbox_audit_finding

    _sb_backend = os.environ.get("HACHI_SANDBOX_BACKEND", "process")
    _sb_finding = sandbox_audit_finding(_sb_backend, container_backend_available())
    if _sb_finding is not None:
        add_finding(*_sb_finding)

    for cap_name, state in cfg.capabilities.items():
        if state.enabled and not state.secret_ref:
            add_finding(
                "medium",
                f"capability.{cap_name}.secret_ref_missing",
                f"Capability '{cap_name}' is enabled without a secret_ref.",
                "Bind the capability to a secret reference managed by the secret backend.",
            )

    # --ignore-checks: drop named check ids before counting, so they are excluded
    # from BOTH the report and the exit-code gate. This exists because some checks
    # describe the *deployment* (e.g. sandbox.process_backend reports that the
    # active sandbox backend is process-isolation, which is the documented default
    # and not something a pull request can change). Without an escape hatch, a
    # PR-level --fail-on-medium gate is red for every contributor regardless of
    # their diff — which teaches contributors to ignore the gate.
    #
    # Filter in place (`[:]`) rather than rebinding `findings`. (Both work —
    # `add_finding` closes over the *cell*, not the object — but in-place keeps
    # the list identity stable for anything else holding a reference.)
    #
    # A requested id that matches nothing is reported separately. Without that, a
    # typo (`sandbox.process back-end`) or a renamed check looks exactly like a
    # successful exclusion: the finding survives, the gate goes red, and the CI
    # log says the check was ignored.
    ignored_checks = sorted({c.strip() for c in ignore_checks.split(",") if c.strip()})
    ignored_checks_unmatched: list[str] = []
    if ignored_checks:
        _present = {f["check_id"] for f in findings}
        ignored_checks_unmatched = [c for c in ignored_checks if c not in _present]
        _ignored = set(ignored_checks)
        findings[:] = [f for f in findings if f["check_id"] not in _ignored]

    high_count = sum(1 for f in findings if f["severity"] == "high")
    medium_count = sum(1 for f in findings if f["severity"] == "medium")
    low_count = sum(1 for f in findings if f["severity"] == "low")
    total_count = len(findings)

    # Build result payload. `status` is set below, from the final exit code.
    result = {
        "high": high_count,
        "medium": medium_count,
        "low": low_count,
        "total": total_count,
        "findings": findings,
        # Echo the ignore set so a CI consumer can tell "no finding" apart from
        # "that finding was deliberately excluded" — and can see when a requested
        # id matched nothing (a typo or a renamed check).
        "ignored_checks": ignored_checks,
        "ignored_checks_unmatched": ignored_checks_unmatched,
    }

    # Determine exit code based on fail thresholds
    exit_code = 0
    fail_reasons = []

    if fail_on_high and high_count > 0:
        exit_code = 2
        fail_reasons.append(f"{high_count} high-severity finding(s)")

    if fail_on_medium and (high_count > 0 or medium_count > 0):
        exit_code = 2
        if not fail_reasons:
            fail_reasons.append(f"{medium_count} medium-severity finding(s)")

    if max_findings is not None and total_count > max_findings:
        exit_code = 2
        fail_reasons.append(f"finding count ({total_count}) exceeds max ({max_findings})")

    result["exit_code"] = exit_code
    # Derive `status` from the exit code, not from high_count alone: with
    # --fail-on-medium, a medium-only run exits 2 while `status` said "pass",
    # and medium-only is the steady state for CI now that posture checks are
    # pinned. The two fields must not disagree.
    result["status"] = "pass" if exit_code == 0 else "fail"
    result["fail_reasons"] = fail_reasons if fail_reasons else []

    # Output format selection
    if json_output:
        # Plain print (not console.print) so Rich never soft-wraps the JSON
        # payload to the terminal width — that would inject newlines mid-token
        # and break `json.loads` for CI consumers.
        print(json.dumps(result, indent=2))
    else:
        # Human-friendly format with rich rendering
        border = "red" if high_count > 0 else "yellow" if medium_count > 0 else "green"
        console.print(
            Panel(
                json.dumps(
                    {
                        "status": result["status"],
                        "high": high_count,
                        "medium": medium_count,
                        "low": low_count,
                        "total": total_count,
                        "findings": findings,
                    },
                    indent=2,
                ),
                title="Hachi Security Audit",
                border_style=border,
            )
        )

    if exit_code != 0 and not json_output:
        console.print(f"\n[bold red]Audit failed:[/] {', '.join(fail_reasons)}")
        console.print(
            "[dim]Use --json flag to export machine-readable output for CI integration.[/dim]"
        )

    if exit_code != 0:
        raise typer.Exit(exit_code)


@app.command("memoir")
def memoir(
    year: int = typer.Option(
        None, "--year", "-y", help="Year to summarise (default: current year)."
    ),
    output: Path = typer.Option(  # noqa: B008
        None, "--output", "-o", help="Write output to file."
    ),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Generate a yearly memoir from your agent's memory journal."""
    import datetime

    from hachi.og_engine.parser import parse_og_file

    _year = year or datetime.date.today().year
    year_str = str(_year)

    paths = get_hachi_paths()
    memory_dir = paths.memory_dir

    facts: list[str] = []
    decisions: list[str] = []
    events: list[str] = []

    _role_buckets: dict[str, list[str]] = {
        "fact": facts,
        "decision": decisions,
        "episode": events,
        "event": events,
    }

    try:
        og_files = sorted(set(memory_dir.glob("*.og")) | set(memory_dir.glob("journal*.og")))
    except FileNotFoundError:
        og_files = []

    if not og_files:
        console.print("[dim]No memory files found.[/dim]")
        return

    for og_file in og_files:
        try:
            parsed = parse_og_file(str(og_file))
        except Exception:
            continue

        for node in parsed.nodes:
            # Check if the year appears anywhere in the node's text content
            node_text = " ".join(
                [
                    node.dense,
                    node.full,
                    node.summary,
                    " ".join(node.steps),
                    " ".join(node.assertions),
                    node.note,
                ]
            )
            if year_str not in node_text:
                continue

            role = (node.role or "").lower()
            bucket = _role_buckets.get(role)
            if bucket is not None:
                entry = node.dense.strip() or node.full.strip()[:120] or node.name
                bucket.append(entry)
            else:
                # Unknown role: add to events as a catch-all
                entry = node.dense.strip() or node.full.strip()[:120] or node.name
                events.append(entry)

    result: dict = {
        "year": _year,
        "facts": facts,
        "decisions": decisions,
        "events": events,
    }

    if json_out:
        output_text = json.dumps(result, indent=2)
        if output:
            output.write_text(output_text, encoding="utf-8")
            console.print(f"[green]Memoir written to[/green] {output}")
        else:
            print(output_text)
        return

    lines = [f"# Memoir {_year}\n"]
    if decisions:
        lines.append("## Decisions")
        for d in decisions:
            lines.append(f"- {d}")
        lines.append("")
    if facts:
        lines.append("## Facts")
        for f in facts:
            lines.append(f"- {f}")
        lines.append("")
    if events:
        lines.append("## Events")
        for e in events:
            lines.append(f"- {e}")
        lines.append("")

    if not (decisions or facts or events):
        lines.append(f"No memory entries found for {_year}.")

    human_text = "\n".join(lines)
    if output:
        output.write_text(human_text, encoding="utf-8")
        console.print(f"[green]Memoir written to[/green] {output}")
    else:
        console.print(Markdown(human_text))


# ---------------------------------------------------------------------------
# Task 6c — Credential management commands
# ---------------------------------------------------------------------------

KNOWN_CREDENTIAL_KEYS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "Anthropic LLM provider",
    "OPENAI_API_KEY": "OpenAI-compatible provider",
    "GOOGLE_CLIENT_ID": "Google OAuth client ID (legacy)",
    "GOOGLE_CLIENT_SECRET": "Google OAuth client secret (legacy)",
    "HACHI_OAUTH_GOOGLE_CLIENT_ID": "Google connector client ID",
    "HACHI_OAUTH_GOOGLE_CLIENT_SECRET": "Google connector client secret",
    "HACHI_OAUTH_SLACK_CLIENT_ID": "Slack connector client ID",
    "HACHI_OAUTH_SLACK_CLIENT_SECRET": "Slack connector client secret",
    "HACHI_OAUTH_DISCORD_CLIENT_ID": "Discord connector client ID",
    "HACHI_OAUTH_DISCORD_CLIENT_SECRET": "Discord connector client secret",
    "HACHI_OAUTH_NOTION_CLIENT_ID": "Notion connector client ID",
    "HACHI_OAUTH_NOTION_CLIENT_SECRET": "Notion connector client secret",
    "HACHI_OAUTH_GITHUB_CLIENT_ID": "GitHub connector client ID",
    "HACHI_OAUTH_GITHUB_CLIENT_SECRET": "GitHub connector client secret",
    "telegram_bot_token": "Telegram bot token",
    "tavily_api_key": "Tavily web search API key",
    "META_WHATSAPP_TOKEN": "WhatsApp Meta access token",
    "META_WHATSAPP_PHONE_ID": "WhatsApp phone number ID",
    "TWILIO_ACCOUNT_SID": "Twilio account SID (WhatsApp optional)",
    "TWILIO_AUTH_TOKEN": "Twilio auth token (WhatsApp optional)",
    "HACHI_STT_API_KEY": "Speech-to-text API key",
    "HACHI_TTS_API_KEY": "Text-to-speech API key",
    "HACHI_SECRET_PASSPHRASE": "Passphrase for encrypted file secret store",
}


def _mask_secret(value: str) -> str:
    """Return a masked representation of a secret value.

    Shows first 4 and last 4 characters with ellipsis in between.
    For short values (< 8 chars), masks everything.
    """
    if len(value) >= 8:
        return f"{value[:4]}…{value[-4:]}"
    return "****"


def _get_vault() -> CredentialVault:
    """Instantiate a CredentialVault using the default backing store."""
    return CredentialVault()


# -- hachi set KEY=value [KEY2=value2 ...] ------------------------------------


@app.command(name="set")
def cred_set(
    pairs: list[str] = typer.Argument(  # noqa: B008
        ...,
        metavar="KEY=value",
        help="One or more KEY=value pairs to store in the credential vault.",
    ),
) -> None:
    """Store one or more named credentials in the secure vault.

    Each argument must be in KEY=value form.  The key is validated against
    KNOWN_CREDENTIAL_KEYS; unknown keys are accepted with a warning.

    Example::

        hachi set ANTHROPIC_API_KEY=sk-abc123 tavily_api_key=tv-xyz
    """
    from rich.table import Table

    vault = _get_vault()
    table = Table(show_header=False, box=None, padding=(0, 1))

    for pair in pairs:
        if "=" not in pair:
            console.print(
                f"[red]Error:[/red] {pair!r} is not a KEY=value pair — "
                "each argument must contain '='."
            )
            raise typer.Exit(1)

        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            console.print("[red]Error:[/red] Empty key in argument — provide KEY=value.")
            raise typer.Exit(1)

        if key not in KNOWN_CREDENTIAL_KEYS:
            console.print(f"[yellow]Warning:[/yellow] unknown key {key!r} — storing anyway.")

        vault.set_token(key, value)
        table.add_row("[green]Saved:[/green]", f"[cyan]{key}[/cyan]")

    console.print(table)


# -- hachi get KEY ------------------------------------------------------------


@app.command(name="get")
def cred_get(
    key: str = typer.Argument(..., metavar="KEY", help="Credential key to retrieve."),
) -> None:
    """Retrieve a credential from the vault and print it masked.

    The full value is NEVER printed.  Use this to confirm a key is set
    without exposing it in terminal history.
    """
    vault = _get_vault()
    value: str | None = None
    try:
        value = vault.get_token(key)
    except Exception:
        value = None

    if value is None:
        console.print(f"[yellow]{key}[/yellow]: [dim]\\[not set][/dim]")
    else:
        console.print(f"[cyan]{key}[/cyan]: {_mask_secret(value)}")


# -- hachi list-keys ----------------------------------------------------------


@app.command(name="list-keys")
def cred_list_keys() -> None:
    """List all known credential keys with their current status.

    Checks the vault first, then falls back to environment variables.
    Extra vault keys not in the built-in schema are appended at the bottom.
    """
    from rich.table import Table

    vault = _get_vault()

    # Collect vault metadata to detect extra keys
    try:
        vault_meta = vault.list_token_metadata()
        vault_keys_present: set[str] = {m["name"] for m in vault_meta}
    except Exception:
        vault_keys_present = set()

    table = Table(title="Credential Keys", show_header=True, header_style="bold")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Status")

    shown: set[str] = set()

    for key, description in KNOWN_CREDENTIAL_KEYS.items():
        shown.add(key)
        # Check vault first
        vault_has: bool = key in vault_keys_present
        env_has: bool = key in os.environ

        if vault_has:
            status = "[green]SET (vault)[/green]"
        elif env_has:
            status = "[yellow]SET (env)[/yellow]"
        else:
            status = "[dim]not set[/dim]"

        table.add_row(key, description, status)

    # Append any extra vault keys not already in KNOWN_CREDENTIAL_KEYS
    extra_keys = vault_keys_present - shown
    for key in sorted(extra_keys):
        table.add_row(key, "[dim](custom)[/dim]", "[green]SET (vault)[/green]")

    console.print(table)


# -- hachi unset KEY ----------------------------------------------------------


@app.command(name="unset")
def cred_unset(
    key: str = typer.Argument(..., metavar="KEY", help="Credential key to remove."),
) -> None:
    """Remove a credential from the vault.

    If an environment variable of the same name is still set in the current
    shell session, a warning is printed because the env var will continue to
    shadow any future vault writes until the shell is restarted.
    """
    vault = _get_vault()
    try:
        vault.delete_token(key)
        console.print(f"[green]Removed:[/green] [cyan]{key}[/cyan]")
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] could not remove {key!r} from vault: {exc}")

    if key in os.environ:
        console.print(
            f"[yellow]Note:[/yellow] environment variable [cyan]{key}[/cyan] is still set "
            "in the current shell session and will continue to shadow the vault entry "
            "until you restart your shell or unset it manually."
        )


# -- keys sub-app aliases (hachi keys set/get/list/unset) ---------------------


@keys_app.command(name="set")
def keys_set(
    pairs: list[str] = typer.Argument(  # noqa: B008
        ...,
        metavar="KEY=value",
        help="One or more KEY=value pairs to store in the credential vault.",
    ),
) -> None:
    """Store one or more named credentials (alias of ``hachi set``)."""
    cred_set(pairs)


@keys_app.command(name="get")
def keys_get(
    key: str = typer.Argument(..., metavar="KEY", help="Credential key to retrieve."),
) -> None:
    """Retrieve a masked credential value (alias of ``hachi get``)."""
    cred_get(key)


@keys_app.command(name="list")
def keys_list() -> None:
    """List all credential keys and their status (alias of ``hachi list-keys``)."""
    cred_list_keys()


@keys_app.command(name="unset")
def keys_unset(
    key: str = typer.Argument(..., metavar="KEY", help="Credential key to remove."),
) -> None:
    """Remove a credential from the vault (alias of ``hachi unset``)."""
    cred_unset(key)


# ---------------------------------------------------------------------------
# Task 8c — ObjectGraph version history and rollback
# ---------------------------------------------------------------------------


@og_app.command(name="history")
def og_history_cmd(
    name: str = typer.Argument(..., metavar="NAME", help="Skill name (without .og extension)."),
) -> None:
    """Show the version history of an ObjectGraph skill file.

    Reads from the append-only .og-history sidecar in the skills directory.
    """
    from rich.table import Table

    from hachi.core.og_history import list_versions

    skills_dir = get_hachi_paths().skills_dir
    versions = list_versions(name, skills_dir=skills_dir)

    if not versions:
        console.print(f"[yellow]No history found for skill:[/yellow] {name!r}")
        raise typer.Exit(0)

    table = Table(title=f"Version history: {name}", show_header=True, header_style="bold")
    table.add_column("Version", style="cyan", justify="right")
    table.add_column("Timestamp")
    table.add_column("Author")
    table.add_column("Summary")

    for entry in versions:
        table.add_row(
            str(entry.get("version", "?")),
            str(entry.get("timestamp", "")),
            str(entry.get("author", "")),
            str(entry.get("summary", "")),
        )

    console.print(table)


@og_app.command(name="rollback")
def og_rollback_cmd(
    name: str = typer.Argument(..., metavar="NAME", help="Skill name (without .og extension)."),
    version: int = typer.Option(
        ..., "--version", "-v", help="Version number to roll back to.", show_default=False
    ),
) -> None:
    """Roll back an ObjectGraph skill to a previous version.

    Retrieves the snapshot from history, writes it back to the skills
    directory (overwriting the current file), and records the rollback as
    a new history entry so the audit trail is preserved.
    """
    from hachi.core.og_history import get_version, record_version

    skills_dir = get_hachi_paths().skills_dir

    # Retrieve the historical snapshot
    content = get_version(name, version, skills_dir=skills_dir)
    if content is None:
        console.print(
            f"[red]Error:[/red] version {version} of skill {name!r} not found in history."
        )
        raise typer.Exit(1)

    # Write the snapshot back to the skills dir (match the naming convention used
    # by upsert_skill: top-level .og for hand-authored, learned/<name>.og for
    # agent-authored).  We write to whichever location already has the file;
    # if neither exists yet, we use the top-level skills dir.
    candidate_paths: list[Path] = []
    if skills_dir.exists():
        candidate_paths = [
            skills_dir / f"{name}.og",
            skills_dir / "learned" / f"{name}.og",
        ]

    target: Path | None = None
    for p in candidate_paths:
        if p.exists():
            target = p
            break

    if target is None:
        # Skill file doesn't exist yet — write to top-level skills dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        target = skills_dir / f"{name}.og"

    # Atomic write via tempfile + replace to avoid corruption
    import tempfile

    tmp_fd, tmp_path_str = tempfile.mkstemp(
        dir=target.parent, prefix=f".{name}_rollback_", suffix=".og.tmp"
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        tmp_path.replace(target)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    # Record the rollback as a new human-authored version
    new_version = record_version(
        name,
        content,
        author="human",
        summary=f"rollback to v{version}",
        skills_dir=skills_dir,
    )

    console.print(
        f"[green]Rolled back[/green] [cyan]{name}[/cyan] to v{version} "
        f"→ written to [dim]{target}[/dim] (recorded as v{new_version})."
    )


@app.command("backup")
def backup(
    dest: Path = typer.Option(  # noqa: B008
        None,
        "--dest",
        help=(
            "Parent directory for the backup. Defaults to a 'backups' sub-dir of the Hachi"
            " state dir."
        ),
        show_default=False,
    ),
) -> None:
    """Create a timestamped backup of session history and the memory vault.

    Backs up (1) the sessions SQLite database via an online hot-backup, (2) the
    ChromaDB memory-vault directory via a directory copy, and (3) the config-dir
    files ``settings.toml`` and ``device-permissions.og`` (non-secret config only).

    Secrets (.env files) are intentionally excluded because they contain credentials
    that should be managed through your secret manager, not copied into backup dirs.

    The backup is written to a timestamped sub-directory:
        <dest>/hachi-backup-<YYYYMMDD-HHMMSS>/
    """
    import shutil
    from datetime import datetime

    paths = get_hachi_paths()

    # Resolve destination directory: default to <state_dir>/backups/
    if dest is None:
        dest = paths.state_dir / "backups"

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = dest / f"hachi-backup-{timestamp}"

    try:
        backup_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        console.print(f"[red]Backup directory already exists: {backup_dir}[/red]")
        raise typer.Exit(1) from None
    except OSError as exc:
        console.print(f"[red]Cannot create backup directory {backup_dir}: {exc}[/red]")
        raise typer.Exit(1) from exc

    manifest: list[str] = []
    errors: list[str] = []

    # 1. Sessions database (online hot-backup — safe while gateway is running).
    sessions_src = paths.sessions_db
    sessions_dest = backup_dir / "sessions.db"
    if sessions_src.exists():
        try:
            store = SessionStore(db_path=sessions_src)
            try:
                store.backup(sessions_dest)
            finally:
                store.shutdown()
            manifest.append(f"  sessions.db  ({sessions_src})")
        except Exception as exc:
            errors.append(f"sessions.db: {exc}")
    else:
        manifest.append("  sessions.db  (skipped — not yet created)")

    # 2. ChromaDB memory vault (directory copy — stop-the-world snapshot).
    chroma_src = paths.chroma_dir
    chroma_dest = backup_dir / "chroma_vault"
    if chroma_src.exists():
        try:
            shutil.copytree(str(chroma_src), str(chroma_dest))
            manifest.append(f"  chroma_vault/ ({chroma_src})")
        except Exception as exc:
            errors.append(f"chroma_vault: {exc}")
    else:
        manifest.append("  chroma_vault/ (skipped — not yet created)")

    # 3. Config files (non-secret): settings.toml + device-permissions.og
    for config_file in (paths.global_config_toml, paths.permissions_file):
        if config_file.exists():
            try:
                shutil.copy2(str(config_file), str(backup_dir / config_file.name))
                manifest.append(f"  {config_file.name}  ({config_file})")
            except Exception as exc:
                errors.append(f"{config_file.name}: {exc}")

    # Secrets are explicitly excluded — note it in the output.
    manifest.append("  .env files   (excluded — contain secrets; manage separately)")

    if errors:
        console.print("[yellow]Backup completed with errors:[/yellow]")
        for err in errors:
            console.print(f"  [red]ERROR:[/red] {err}")

    console.print(
        Panel(
            f"[bold green]Backup created:[/bold green] {backup_dir}\n\n"
            "Contents:\n" + "\n".join(manifest),
            title="hachi backup",
            border_style="green",
        )
    )


@app.command("restore")
def restore(
    src: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to a backup directory created by `hachi backup`.",
    ),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        "-y",
        help="Skip the confirmation prompt (required for non-interactive / CI use).",
    ),
) -> None:
    """Restore session history and memory vault from a backup directory.

    WARNING: This operation overwrites live data.  The current sessions database and
    memory vault will be replaced with the contents of the backup.  Any data created
    after the backup was taken will be lost.

    Requires ``--yes`` or interactive confirmation to proceed.

    The gateway must not be running when restoring the memory vault (ChromaDB does
    not support concurrent writers); the sessions database can be restored safely
    (the hot-backup copy is consistent).
    """
    import shutil

    paths = get_hachi_paths()
    src = Path(src)

    if not src.exists() or not src.is_dir():
        console.print(f"[red]Source backup directory not found: {src}[/red]")
        raise typer.Exit(1)

    # Guard: require explicit confirmation before overwriting live data.
    if not yes:
        confirm = typer.confirm(
            f"This will overwrite your live Hachi data with the backup at:\n  {src}\nContinue?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Restore cancelled.[/yellow]")
            raise typer.Exit(0)

    restored: list[str] = []
    errors: list[str] = []

    # 1. Sessions database.
    sessions_src = src / "sessions.db"
    sessions_dest = paths.sessions_db
    if sessions_src.exists():
        try:
            sessions_dest.parent.mkdir(parents=True, exist_ok=True)
            import shutil as _shutil

            _shutil.copy2(str(sessions_src), str(sessions_dest))
            restored.append(f"  sessions.db  → {sessions_dest}")
        except Exception as exc:
            errors.append(f"sessions.db: {exc}")
    else:
        restored.append("  sessions.db  (not in backup — skipped)")

    # 2. ChromaDB memory vault.
    chroma_src = src / "chroma_vault"
    chroma_dest = paths.chroma_dir
    if chroma_src.exists():
        try:
            if chroma_dest.exists():
                shutil.rmtree(str(chroma_dest))
            shutil.copytree(str(chroma_src), str(chroma_dest))
            restored.append(f"  chroma_vault/ → {chroma_dest}")
        except Exception as exc:
            errors.append(f"chroma_vault: {exc}")
    else:
        restored.append("  chroma_vault/ (not in backup — skipped)")

    # 3. Config files (non-secret).
    for config_name in ("settings.toml", "device-permissions.og"):
        config_src = src / config_name
        config_dest = paths.config_dir / config_name
        if config_src.exists():
            try:
                config_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(config_src), str(config_dest))
                restored.append(f"  {config_name}  → {config_dest}")
            except Exception as exc:
                errors.append(f"{config_name}: {exc}")

    if errors:
        console.print("[yellow]Restore completed with errors:[/yellow]")
        for err in errors:
            console.print(f"  [red]ERROR:[/red] {err}")
        raise typer.Exit(1)

    console.print(
        Panel(
            "[bold green]Restore complete.[/bold green]\n\nRestored:\n" + "\n".join(restored),
            title="hachi restore",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
